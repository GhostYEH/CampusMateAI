export class AppState {
  sessionToken: string = '';
  darkMode: boolean = false;
  reduceMotion: boolean = false;

  restore(): void {
    this.sessionToken = AppStorage.get<string>('sessionToken') ?? '';
    this.darkMode = AppStorage.get<boolean>('darkMode') ?? false;
    this.reduceMotion = AppStorage.get<boolean>('reduceMotion') ?? false;
  }

  signIn(token: string): void {
    this.sessionToken = token;
    AppStorage.setOrCreate('sessionToken', token);
  }

  signOut(): void {
    this.sessionToken = '';
    AppStorage.setOrCreate('sessionToken', '');
  }

  toggleTheme(): void {
    this.darkMode = !this.darkMode;
    AppStorage.setOrCreate('darkMode', this.darkMode);
  }

  setReduceMotion(value: boolean): void {
    this.reduceMotion = value;
    AppStorage.setOrCreate('reduceMotion', value);
  }
}
