import React from "react";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import * as api from "../../data/api.js";
import { formatDateTime } from "../../utils/date.js";
import {
  MATERIALS_PAGE_LIMIT,
  MAX_UPLOAD_BYTES,
  describeExtractionStatus,
  describeMaterialError,
  formatBytes,
  nextCursorOf,
  normalizeMaterialDetail,
  normalizeMaterialList,
  upsertMaterial,
  validateUploadCandidate,
} from "../../features/openmaic/materialsModel.js";

const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");

/**
 * 课程内的资料。
 *
 * 只在服务端真实上报 `material` 能力时由父组件渲染。两条界面纪律：
 *
 * - **没有正文的资料不显示正文区。** `unsupported` 的条目给出原因，而不是一块
 *   空白，否则"解析不了"会被读成"这个文件是空的"。
 * - **重试复用同一个幂等键。** 上传失败但可重试时保留键，换文件或被拒时才丢弃，
 *   否则重试会真的产生第二份资料。
 */
export default function MaterialsPanel({ courseId, canManageMaterials = false }) {
  const [materials, setMaterials] = React.useState([]);
  const [cursor, setCursor] = React.useState(null);
  const [loading, setLoading] = React.useState(canManageMaterials);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [notice, setNotice] = React.useState("");
  const [detail, setDetail] = React.useState(null);
  const [detailLoading, setDetailLoading] = React.useState(false);
  const [localReject, setLocalReject] = React.useState("");
  const inputRef = React.useRef(null);
  // 同一个用户动作重试必须复用同一个幂等键。
  const pendingKey = React.useRef(null);

  const load = React.useCallback(async ({ append = false, cursor: pageCursor = null } = {}) => {
    if (!canManageMaterials) return;
    setLoading(true);
    setError("");
    try {
      const payload = await api.listOpenMAICMaterials(courseId, {
        limit: MATERIALS_PAGE_LIMIT,
        cursor: pageCursor,
      });
      const next = normalizeMaterialList(payload);
      setMaterials((previous) => (append ? [...previous, ...next] : next));
      setCursor(nextCursorOf(payload));
    } catch (failure) {
      setError(describeMaterialError(failure).message);
    } finally {
      setLoading(false);
    }
  }, [canManageMaterials, courseId]);

  React.useEffect(() => {
    setMaterials([]);
    setCursor(null);
    setDetail(null);
    setNotice("");
    setLocalReject("");
    pendingKey.current = null;
    if (inputRef.current) inputRef.current.value = "";
    void load();
  }, [courseId, load]);

  async function submit(event) {
    event.preventDefault();
    const file = inputRef.current?.files?.[0] || null;
    const rejected = validateUploadCandidate(file);
    if (rejected) {
      setLocalReject(rejected);
      return;
    }
    if (busy) return;
    setBusy(true);
    setLocalReject("");
    setError("");
    setNotice("");
    pendingKey.current = pendingKey.current || api.newIdempotencyKey();
    try {
      const created = normalizeMaterialList({ items: [await api.uploadOpenMAICMaterial(courseId, {
        file,
        idempotencyKey: pendingKey.current,
      })] })[0];
      pendingKey.current = null;
      if (inputRef.current) inputRef.current.value = "";
      setMaterials((previous) => upsertMaterial(previous, created));
      const described = describeExtractionStatus(created?.extractionStatus);
      setNotice(
        created?.deduplicated
          ? `「${created.filename}」已经在课程资料里，没有重复添加。`
          : created?.extractionStatus === "extracted"
            ? `已上传「${created.filename}」，解析出 ${created.textChars} 个字符。`
            : `已上传「${created.filename}」：${described.label}。${described.hint}`,
      );
    } catch (failure) {
      const described = describeMaterialError(failure);
      // 只有"这次文件本身有问题"才弃键；可重试的失败必须复用同一个键。
      if (!described.retryable) pendingKey.current = null;
      setError(described.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(material) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api.deleteOpenMAICMaterial(courseId, material.id, { revision: material.revision });
      setMaterials((previous) => previous.filter((item) => item.id !== material.id));
      if (detail?.id === material.id) setDetail(null);
      setNotice(`已删除「${material.filename}」`);
    } catch (failure) {
      const described = describeMaterialError(failure);
      setError(described.message);
      // 409 说明本地副本过期：重新读取是唯一能继续的动作。
      if (described.kind === "conflict") await load();
    } finally {
      setBusy(false);
    }
  }

  async function open(material) {
    if (detailLoading) return;
    setError("");
    // 解析不了的资料没有正文可取；直接给出原因，而不是发一次注定为空的请求。
    if (material.extractionStatus !== "extracted") {
      setDetail({ ...material, text: "" });
      return;
    }
    setDetailLoading(true);
    try {
      const payload = await api.getOpenMAICMaterial(courseId, material.id);
      setDetail(normalizeMaterialDetail(payload) || { ...material, text: "" });
    } catch (failure) {
      setError(describeMaterialError(failure).message);
    } finally {
      setDetailLoading(false);
    }
  }

  if (!canManageMaterials) return null;

  return <Panel className="openmaic-materials-panel">
    <SectionHeading title="课程资料" detail={`上传后由服务端解析正文，单个文件上限 ${formatBytes(MAX_UPLOAD_BYTES)}`} />

    {notice ? <p className="openmaic-materials__notice" role="status">{notice}</p> : null}
    {error ? <p className="openmaic-materials__error" role="alert">{error}</p> : null}
    {localReject ? <p className="openmaic-materials__error" role="alert">{localReject}</p> : null}

    <form className="openmaic-materials__upload" onSubmit={submit}>
      <label className="openmaic-materials__picker">
        <Icon name="PhFileText" size={18} />
        <input
          ref={inputRef}
          type="file"
          aria-label="选择要上传的课程资料"
          onChange={(event) => setLocalReject(validateUploadCandidate(event.target.files?.[0]) || "")}
        />
      </label>
      <Button type="submit" disabled={busy}>{busy ? "上传中" : "上传并解析"}</Button>
    </form>

    {loading && !materials.length ? <p className="muted-copy">正在读取课程资料…</p>
      : materials.length ? <ul className="openmaic-materials">
        {materials.map((material) => {
          const described = describeExtractionStatus(material.extractionStatus);
          return <li className="openmaic-material" key={material.id}>
            <div className="openmaic-material__row">
              <Icon name="PhFileText" size={18} />
              <span className="openmaic-material__name">{material.filename}</span>
              <span className={`openmaic-material__status openmaic-material__status--${described.tone}`}>
                {described.label}
              </span>
              <small>{formatBytes(material.byteSize)}</small>
              <small>{material.extractionStatus === "extracted" ? `${material.textChars} 字符` : described.hint}</small>
              <small>{dateText(material.updatedAt)}</small>
              <Button type="button" variant="secondary" disabled={busy} onClick={() => open(material)}>
                {material.extractionStatus === "extracted" ? "查看正文" : "查看说明"}
              </Button>
              <Button type="button" variant="secondary" disabled={busy} onClick={() => remove(material)}>删除</Button>
            </div>
          </li>;
        })}
      </ul>
      : <div className="openmaic-home__empty openmaic-home__empty--wide">
        <Icon name="PhFileText" size={26} />
        <div><strong>还没有课程资料</strong><p>上传讲义或论文后，这里会显示每份资料真实的解析状态。</p></div>
      </div>}

    {cursor ? <Button type="button" variant="secondary" disabled={loading}
      onClick={() => load({ append: true, cursor })}>加载更多</Button> : null}

    {detailLoading ? <p className="muted-copy">正在读取正文…</p> : null}

    {detail ? <div className="openmaic-material-detail">
      <div className="openmaic-material-detail__head">
        <strong>{detail.filename}</strong>
        <small>{detail.mediaType}</small>
        <Button type="button" variant="secondary" onClick={() => setDetail(null)}>收起</Button>
      </div>
      {detail.extractionStatus === "extracted"
        ? <pre className="openmaic-material-detail__text">{detail.text}</pre>
        : <p className="muted-copy">
          {describeExtractionStatus(detail.extractionStatus).hint || "这份资料没有可显示的正文。"}
        </p>}
    </div> : null}
  </Panel>;
}
