/**
 * A minimal, deliberately narrow ZIP codec built on `node:zlib` only.
 *
 * The managed service ships **zero npm dependencies** on purpose (its test suite
 * runs with no install, and a smaller dependency surface is a smaller supply
 * chain). `.maic.zip` is our own archive format, so the container can be read
 * and written with the standard library — the same trade the DSL port already
 * made.
 *
 * A hand-written container reader is exactly where a serializer becomes a
 * vulnerability, so every rejection here is a named rule rather than a best
 * effort:
 *
 * - **No path escape.** A name that is absolute, carries a drive letter, uses a
 *   backslash, contains a `.`/`..` segment, is empty, or holds a control
 *   character is refused outright. Nothing is ever written to disk by this
 *   module, but the names travel to a caller that will name files with them.
 * - **No zip bombs.** Entry count, per-entry uncompressed size and total
 *   uncompressed size are all bounded *before* inflating, using the sizes the
 *   directory declares, and the declared size is then checked against what the
 *   inflater actually produced.
 * - **No silent corruption.** The CRC-32 and the declared uncompressed size of
 *   every entry are verified. A mismatch is an error, not a warning.
 * - **No unsupported features read as if supported.** Encryption, Zip64 and any
 *   compression method other than stored/deflate are refused by name instead of
 *   being mis-parsed into plausible-looking output.
 */

import { deflateRawSync, inflateRawSync } from 'node:zlib';

import { WorkspaceError } from '../workspace/errors.ts';

export const ZIP_LIMITS = {
  /** Entries in one archive. A stage archive needs two; the rest is asset headroom. */
  maxEntries: 64,
  /** Bytes of one entry after inflation. Must stay above `DSL_LIMITS.maxDocumentBytes`. */
  maxEntryBytes: 4 * 1024 * 1024,
  /** Bytes of all entries after inflation — the zip-bomb bound. */
  maxTotalBytes: 8 * 1024 * 1024,
  /** Bytes of one entry name. */
  maxNameBytes: 255,
} as const;

const EOCD_SIGNATURE = 0x06054b50;
const CENTRAL_SIGNATURE = 0x02014b50;
const LOCAL_SIGNATURE = 0x04034b50;
const EOCD_MIN_BYTES = 22;
const CENTRAL_MIN_BYTES = 46;
const LOCAL_MIN_BYTES = 30;
/** The EOCD is at the end, after at most a 64 KiB comment. */
const MAX_COMMENT_BYTES = 0xffff;

const METHOD_STORED = 0;
const METHOD_DEFLATE = 8;

const FLAG_ENCRYPTED = 0x0001;

/** Sentinel sizes meaning "look at the Zip64 record"; refused, never guessed. */
const ZIP64_SENTINEL = 0xffffffff;
const ZIP64_COUNT_SENTINEL = 0xffff;

export interface ZipEntry {
  name: string;
  data: Buffer;
}

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[index] = value >>> 0;
  }
  return table;
})();

export function crc32(buffer: Buffer): number {
  let crc = 0xffffffff;
  for (let index = 0; index < buffer.length; index += 1) {
    crc = CRC_TABLE[(crc ^ buffer[index]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

/**
 * True when a name is safe to hand to a caller that will turn it into a file.
 *
 * `npm`-style directory entries (names ending in `/`) are *not* accepted: this
 * format has no directories, and silently dropping them would let a crafted
 * archive claim entries it does not have.
 */
export function isSafeEntryName(name: string): boolean {
  if (name.length === 0) return false;
  if (Buffer.byteLength(name, 'utf8') > ZIP_LIMITS.maxNameBytes) return false;
  if (name.includes('\\')) return false;
  if (name.startsWith('/')) return false;
  if (/^[A-Za-z]:/.test(name)) return false;
  if (name.endsWith('/')) return false;
  // Control characters would make the name render differently than it stores.
  // eslint-disable-next-line no-control-regex
  if (/[\u0000-\u001f\u007f]/.test(name)) return false;
  return name.split('/').every((segment) => segment !== '' && segment !== '.' && segment !== '..');
}

function reject(message: string): never {
  throw new WorkspaceError('document_rejected', message);
}

function invalid(message: string): never {
  throw new WorkspaceError('invalid_request', message);
}

/**
 * Read every entry of an archive into memory.
 *
 * Throws {@link WorkspaceError}: `invalid_request` when the bytes are not a zip
 * at all, `document_rejected` when they are a zip this service refuses to
 * accept (unsafe name, bomb shape, unsupported feature, failed integrity check).
 */
export function readZip(archive: Buffer): ZipEntry[] {
  if (archive.length < EOCD_MIN_BYTES) invalid('archive is too small to be a zip');
  const eocd = findEocd(archive);

  const totalEntries = archive.readUInt16LE(eocd + 10);
  const centralSize = archive.readUInt32LE(eocd + 12);
  const centralOffset = archive.readUInt32LE(eocd + 16);

  if (totalEntries === ZIP64_COUNT_SENTINEL || centralSize === ZIP64_SENTINEL || centralOffset === ZIP64_SENTINEL) {
    reject('zip64 archives are not supported');
  }
  if (totalEntries > ZIP_LIMITS.maxEntries) {
    reject(`archive holds more than ${ZIP_LIMITS.maxEntries} entries`);
  }
  if (centralOffset + centralSize > archive.length) {
    invalid('central directory points outside the archive');
  }

  const entries: ZipEntry[] = [];
  const seen = new Set<string>();
  let totalBytes = 0;
  let cursor = centralOffset;

  for (let index = 0; index < totalEntries; index += 1) {
    if (cursor + CENTRAL_MIN_BYTES > archive.length) invalid('central directory is truncated');
    if (archive.readUInt32LE(cursor) !== CENTRAL_SIGNATURE) invalid('central directory entry is malformed');

    const madeBy = archive.readUInt16LE(cursor + 4);
    const flags = archive.readUInt16LE(cursor + 8);
    const method = archive.readUInt16LE(cursor + 10);
    const declaredCrc = archive.readUInt32LE(cursor + 16);
    const compressedSize = archive.readUInt32LE(cursor + 20);
    const uncompressedSize = archive.readUInt32LE(cursor + 24);
    const nameLength = archive.readUInt16LE(cursor + 28);
    const extraLength = archive.readUInt16LE(cursor + 30);
    const commentLength = archive.readUInt16LE(cursor + 32);
    const externalAttributes = archive.readUInt32LE(cursor + 38);
    const localOffset = archive.readUInt32LE(cursor + 42);

    const nameStart = cursor + CENTRAL_MIN_BYTES;
    const nameEnd = nameStart + nameLength;
    if (nameEnd > archive.length) invalid('central directory entry name is truncated');
    const name = archive.toString('utf8', nameStart, nameEnd);

    cursor = nameEnd + extraLength + commentLength;

    if (flags & FLAG_ENCRYPTED) reject(`entry is encrypted: ${name}`);
    if (compressedSize === ZIP64_SENTINEL || uncompressedSize === ZIP64_SENTINEL) {
      reject(`entry uses zip64 sizes: ${name}`);
    }
    if (method !== METHOD_STORED && method !== METHOD_DEFLATE) {
      reject(`entry uses an unsupported compression method (${method}): ${name}`);
    }
    if (!isSafeEntryName(name)) reject(`entry name is not safe: ${name}`);
    if (seen.has(name)) reject(`duplicate entry name: ${name}`);
    seen.add(name);

    // A symlink entry is only meaningful to a caller that extracts to disk.
    // This format has no such concept, so it is refused rather than flattened
    // into a regular file that silently loses its meaning.
    const madeByUnix = madeBy >> 8 === 3;
    if (madeByUnix && (externalAttributes >>> 16) & 0xf000) {
      const fileType = (externalAttributes >>> 16) & 0xf000;
      if (fileType === 0xa000) reject(`entry is a symbolic link: ${name}`);
    }

    if (uncompressedSize > ZIP_LIMITS.maxEntryBytes) {
      reject(`entry exceeds ${ZIP_LIMITS.maxEntryBytes} bytes: ${name}`);
    }
    totalBytes += uncompressedSize;
    if (totalBytes > ZIP_LIMITS.maxTotalBytes) {
      reject(`archive inflates beyond ${ZIP_LIMITS.maxTotalBytes} bytes`);
    }

    entries.push({
      name,
      data: readEntryData(archive, { localOffset, method, compressedSize, uncompressedSize, declaredCrc, name }),
    });
  }

  return entries;
}

function findEocd(archive: Buffer): number {
  const lowest = Math.max(0, archive.length - EOCD_MIN_BYTES - MAX_COMMENT_BYTES);
  for (let cursor = archive.length - EOCD_MIN_BYTES; cursor >= lowest; cursor -= 1) {
    if (archive.readUInt32LE(cursor) !== EOCD_SIGNATURE) continue;
    const commentLength = archive.readUInt16LE(cursor + 20);
    if (cursor + EOCD_MIN_BYTES + commentLength === archive.length) return cursor;
  }
  invalid('archive has no end-of-central-directory record');
}

function readEntryData(
  archive: Buffer,
  input: {
    localOffset: number;
    method: number;
    compressedSize: number;
    uncompressedSize: number;
    declaredCrc: number;
    name: string;
  },
): Buffer {
  const { localOffset } = input;
  if (localOffset + LOCAL_MIN_BYTES > archive.length) invalid('local header points outside the archive');
  if (archive.readUInt32LE(localOffset) !== LOCAL_SIGNATURE) invalid('local header is malformed');

  const localNameLength = archive.readUInt16LE(localOffset + 26);
  const localExtraLength = archive.readUInt16LE(localOffset + 28);
  const dataStart = localOffset + LOCAL_MIN_BYTES + localNameLength + localExtraLength;
  const dataEnd = dataStart + input.compressedSize;
  if (dataEnd > archive.length) invalid('entry data is truncated');

  const raw = archive.subarray(dataStart, dataEnd);
  let data: Buffer;
  if (input.method === METHOD_STORED) {
    data = Buffer.from(raw);
  } else {
    try {
      data = inflateRawSync(raw);
    } catch {
      reject(`entry failed to inflate: ${input.name}`);
    }
  }

  // The declared size is checked against what actually came out, so a bomb that
  // lies about its size still cannot exceed the bound it promised.
  if (data.length !== input.uncompressedSize) {
    reject(`entry size does not match its directory record: ${input.name}`);
  }
  if (crc32(data) !== input.declaredCrc) {
    reject(`entry failed its integrity check: ${input.name}`);
  }
  return data;
}

function dosDateTime(date: Date): { time: number; date: number } {
  const year = date.getUTCFullYear();
  if (year < 1980 || year > 2107) reject('archive timestamp is outside the representable range');
  return {
    time: (date.getUTCHours() << 11) | (date.getUTCMinutes() << 5) | (date.getUTCSeconds() >> 1),
    date: ((year - 1980) << 9) | ((date.getUTCMonth() + 1) << 5) | date.getUTCDate(),
  };
}

/**
 * Build an archive from in-memory entries.
 *
 * The output is deterministic for a fixed entry list, order and timestamp: the
 * same workspace must produce the same bytes, so an export can be compared and
 * re-exported without a spurious diff.
 */
export function writeZip(entries: readonly ZipEntry[], options: { modifiedAt: Date }): Buffer {
  if (entries.length > ZIP_LIMITS.maxEntries) {
    reject(`archive holds more than ${ZIP_LIMITS.maxEntries} entries`);
  }
  const stamp = dosDateTime(options.modifiedAt);
  const seen = new Set<string>();
  const locals: Buffer[] = [];
  const centrals: Buffer[] = [];
  let offset = 0;

  for (const entry of entries) {
    if (!isSafeEntryName(entry.name)) reject(`entry name is not safe: ${entry.name}`);
    if (seen.has(entry.name)) reject(`duplicate entry name: ${entry.name}`);
    seen.add(entry.name);

    const nameBytes = Buffer.from(entry.name, 'utf8');
    const crc = crc32(entry.data);
    const compressed = deflateRawSync(entry.data, { level: 9 });
    // A stored entry would be larger only for already-incompressible input; the
    // smaller of the two is kept so an export never grows a binary asset.
    const useStored = compressed.length >= entry.data.length;
    const payload = useStored ? entry.data : compressed;
    const method = useStored ? METHOD_STORED : METHOD_DEFLATE;

    const local = Buffer.alloc(LOCAL_MIN_BYTES);
    local.writeUInt32LE(LOCAL_SIGNATURE, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0, 6);
    local.writeUInt16LE(method, 8);
    local.writeUInt16LE(stamp.time, 10);
    local.writeUInt16LE(stamp.date, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(payload.length, 18);
    local.writeUInt32LE(entry.data.length, 22);
    local.writeUInt16LE(nameBytes.length, 26);
    local.writeUInt16LE(0, 28);
    locals.push(local, nameBytes, payload);

    const central = Buffer.alloc(CENTRAL_MIN_BYTES);
    central.writeUInt32LE(CENTRAL_SIGNATURE, 0);
    // Version made by 3<<8 = unix, so the external attributes stay meaningful.
    central.writeUInt16LE((3 << 8) | 20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0, 8);
    central.writeUInt16LE(method, 10);
    central.writeUInt16LE(stamp.time, 12);
    central.writeUInt16LE(stamp.date, 14);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(payload.length, 20);
    central.writeUInt32LE(entry.data.length, 24);
    central.writeUInt16LE(nameBytes.length, 28);
    central.writeUInt16LE(0, 30);
    central.writeUInt16LE(0, 32);
    central.writeUInt16LE(0, 34);
    central.writeUInt16LE(0, 36);
    // `>>> 0` matters: `0o100644 << 16` exceeds 2^31 and JavaScript's `<<`
    // yields a signed 32-bit result, which `writeUInt32LE` rejects.
    central.writeUInt32LE((0o100644 << 16) >>> 0, 38);
    central.writeUInt32LE(offset, 42);
    centrals.push(central, nameBytes);

    offset += LOCAL_MIN_BYTES + nameBytes.length + payload.length;
  }

  const centralBytes = Buffer.concat(centrals);
  const eocd = Buffer.alloc(EOCD_MIN_BYTES);
  eocd.writeUInt32LE(EOCD_SIGNATURE, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(centralBytes.length, 12);
  eocd.writeUInt32LE(offset, 16);
  eocd.writeUInt16LE(0, 20);

  return Buffer.concat([...locals, centralBytes, eocd]);
}
