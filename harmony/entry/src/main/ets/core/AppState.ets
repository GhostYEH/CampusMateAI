import { PreferencesUtil } from '../util/PreferencesUtil';

export class AppState {
  sessionToken: string = '';
  darkMode: boolean = false;
  reduceMotion: boolean = false;
  savedUsername: string = '';
  rememberUsername: boolean = false;

  async restore(): Promise<void> {
    this.sessionToken = await PreferencesUtil.getString('sessionToken');
    this.darkMode = await PreferencesUtil.getBoolean('darkMode');
    this.reduceMotion = await PreferencesUtil.getBoolean('reduceMotion');
    this.savedUsername = await PreferencesUtil.getString('savedUsername');
    this.rememberUsername = await PreferencesUtil.getBoolean('rememberUsername');
  }

  async signIn(token: string): Promise<void> {
    this.sessionToken = token;
    await PreferencesUtil.putString('sessionToken', token);
  }

  async signOut(): Promise<void> {
    this.sessionToken = '';
    await PreferencesUtil.putString('sessionToken', '');
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
