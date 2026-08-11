export class AppState {
    sessionToken: string = '';
    darkMode: boolean = false;
    reduceMotion: boolean = false;
    restore(): void {
        this.sessionToken = AppStorage.get<string>('sessionToken') ?? '';
        this.darkMode = AppStorage.get<boolean>('darkMode') ?? false;
        this.reduceMotion = AppStorage.get<boolean>('reduceMotion') ?? false;
    }
    signIn(b: string): void {
        this.sessionToken = b;
        AppStorage.setOrCreate('sessionToken', b);
    }
    signOut(): void {
        this.sessionToken = '';
        AppStorage.setOrCreate('sessionToken', '');
    }
    toggleTheme(): void {
        this.darkMode = !this.darkMode;
        AppStorage.setOrCreate('darkMode', this.darkMode);
    }
    setReduceMotion(a: boolean): void {
        this.reduceMotion = a;
        AppStorage.setOrCreate('reduceMotion', a);
    }
}
