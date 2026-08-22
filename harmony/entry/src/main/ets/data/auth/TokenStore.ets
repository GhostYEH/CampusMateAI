import { asset } from '@kit.AssetStoreKit';
import { util } from '@kit.ArkTS';
import { BusinessError } from '@kit.BasicServicesKit';

const TOKEN_ALIAS: string = 'campusmate.auth.tokens.v1';

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
}

export class AuthTokensModel implements AuthTokens {
  accessToken: string;
  refreshToken: string;
  constructor(accessToken: string, refreshToken: string) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }
}

export interface TokenStorage {
  load(): Promise<AuthTokens>;
  save(tokens: AuthTokens): Promise<void>;
  clear(): Promise<void>;
}

export class AssetTokenStore implements TokenStorage {
  private readonly encoder: util.TextEncoder = new util.TextEncoder();
  private readonly decoder: util.TextDecoder = new util.TextDecoder();

  async load(): Promise<AuthTokens> {
    const query: asset.AssetMap = new Map<asset.Tag, asset.Value>();
    query.set(asset.Tag.ALIAS, this.encoder.encodeInto(TOKEN_ALIAS));
    query.set(asset.Tag.RETURN_TYPE, asset.ReturnType.ALL);
    try {
      const results: asset.AssetMap[] = await asset.query(query);
      if (results.length === 0) {
        return new AuthTokensModel('', '');
      }
      const secret: asset.Value | undefined = results[0].get(asset.Tag.SECRET);
      if (!(secret instanceof Uint8Array)) {
        return new AuthTokensModel('', '');
      }
      const parsed: AuthTokens = JSON.parse(this.decoder.decodeToString(secret)) as AuthTokens;
      return new AuthTokensModel(parsed.accessToken ?? '', parsed.refreshToken ?? '');
    } catch (error) {
      const businessError: BusinessError = error as BusinessError;
      if (businessError.code === asset.ErrorCode.NOT_FOUND) {
        return new AuthTokensModel('', '');
      }
      throw new Error(businessError.message);
    }
  }

  async save(tokens: AuthTokens): Promise<void> {
    await this.clear();
    if (tokens.accessToken.length === 0 && tokens.refreshToken.length === 0) {
      return;
    }
    const attributes: asset.AssetMap = new Map<asset.Tag, asset.Value>();
    attributes.set(asset.Tag.ALIAS, this.encoder.encodeInto(TOKEN_ALIAS));
    attributes.set(asset.Tag.SECRET, this.encoder.encodeInto(JSON.stringify(tokens)));
    attributes.set(asset.Tag.ACCESSIBILITY, asset.Accessibility.DEVICE_POWERED_ON);
    await asset.add(attributes);
  }

  async clear(): Promise<void> {
    const query: asset.AssetMap = new Map<asset.Tag, asset.Value>();
    query.set(asset.Tag.ALIAS, this.encoder.encodeInto(TOKEN_ALIAS));
    try {
      await asset.remove(query);
    } catch (error) {
      const businessError: BusinessError = error as BusinessError;
      if (businessError.code !== asset.ErrorCode.NOT_FOUND) {
        throw new Error(businessError.message);
      }
    }
  }
}
