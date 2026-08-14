import { PreferencesUtil } from '../util/PreferencesUtil';
import { AssetTokenStore, AuthTokens, AuthTokensModel, TokenStorage } from '../data/auth/TokenStore';

export class AppState {
  sessionToken: string = '';
  accessToken: string = '';
  refreshToken: string = '';
  darkMode: boolean = false;
  reduceMotion: boolean = false;
  savedUsername: string = '';
  rememberUsername: boolean = false;

  private readonly tokenStorage: TokenStorage;

  constructor(tokenStorage: TokenStorage = new AssetTokenStore()) {
    this.tokenStorage = tokenStorage;
  }

  async restore(): Promise<void> {
    let tokens: AuthTokens = await this.tokenStorage.load();
    const legacyAccessToken: string = await PreferencesUtil.getString('sessionToken');
    if (tokens.accessToken.length === 0 && legacyAccessToken.length > 0) {
      tokens = new AuthTokensModel(legacyAccessToken, '');
      await this.tokenStorage.save(tokens);
    }
    await PreferencesUtil.delete('sessionToken');
    this.applyTokens(tokens);
    this.darkMode = await PreferencesUtil.getBoolean('darkMode');
    this.reduceMotion = await PreferencesUtil.getBoolean('reduceMotion');
    this.savedUsername = await PreferencesUtil.getString('savedUsername');
    this.rememberUsername = await PreferencesUtil.getBoolean('rememberUsername');
  }

  async signIn(tokens: AuthTokens): Promise<void> {
    await this.updateTokens(tokens);
  }

  async signOut(): Promise<void> {
    this.applyTokens(new AuthTokensModel('', ''));
    await this.tokenStorage.clear();
    await PreferencesUtil.delete('sessionToken');
  }

  getAccessToken(): string { return this.accessToken; }
  getRefreshToken(): string { return this.refreshToken; }

  async updateTokens(tokens: AuthTokens): Promise<void> {
    this.applyTokens(tokens);
    await this.tokenStorage.save(tokens);
  }

  async clearSession(): Promise<void> {
    await this.signOut();
  }

  private applyTokens(tokens: AuthTokens): void {
    this.accessToken = tokens.accessToken;
    this.refreshToken = tokens.refreshToken;
    this.sessionToken = tokens.accessToken;
  }

  async toggleTheme(): Promise<void> {
    this.darkMode = !this.darkMode;
    await PreferencesUtil.putBoolean('darkMode', this.darkMode);
  }

  async setReduceMotion(value: boolean): Promise<void> {
    this.reduceMotion = value;
    await PreferencesUtil.putBoolean('reduceMotion', value);
  }

  async saveUsername(username: string): Promise<void> {
    if (this.rememberUsername) {
      this.savedUsername = username;
      await PreferencesUtil.putString('savedUsername', username);
    } else {
      this.savedUsername = '';
      await PreferencesUtil.putString('savedUsername', '');
    }
    await PreferencesUtil.putBoolean('rememberUsername', this.rememberUsername);
  }

  async setRememberUsername(value: boolean): Promise<void> {
    this.rememberUsername = value;
    await PreferencesUtil.putBoolean('rememberUsername', value);
    if (!value) {
      this.savedUsername = '';
      await PreferencesUtil.putString('savedUsername', '');
    }
  }
}
