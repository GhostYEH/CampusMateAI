import { preferences } from '@kit.ArkData';
import { BusinessError } from '@kit.BasicServicesKit';

const PREFERENCES_NAME = 'CampusMatePreferences';

export class PreferencesUtil {
  static async putString(key: string, value: string): Promise<void> {
    try {
      const dataPreferences = await preferences.getPreferences(getContext(), PREFERENCES_NAME);
      await dataPreferences.put(key, value);
      await dataPreferences.flush();
    } catch (err) {
      let error = err as BusinessError;
      console.error(`Failed to put preferences. Code:${error.code},message:${error.message}`);
    }
  }

  static async getString(key: string, defaultValue: string = ''): Promise<string> {
    try {
      const dataPreferences = await preferences.getPreferences(getContext(), PREFERENCES_NAME);
      const val = await dataPreferences.get(key, defaultValue) as string;
      return val;
    } catch (err) {
      let error = err as BusinessError;
      console.error(`Failed to get preferences. Code:${error.code},message:${error.message}`);
      return defaultValue;
    }
  }

  static async putBoolean(key: string, value: boolean): Promise<void> {
    try {
      const dataPreferences = await preferences.getPreferences(getContext(), PREFERENCES_NAME);
      await dataPreferences.put(key, value);
      await dataPreferences.flush();
    } catch (err) {
      let error = err as BusinessError;
      console.error(`Failed to put preferences. Code:${error.code},message:${error.message}`);
    }
  }

  static async getBoolean(key: string, defaultValue: boolean = false): Promise<boolean> {
    try {
      const dataPreferences = await preferences.getPreferences(getContext(), PREFERENCES_NAME);
      const val = await dataPreferences.get(key, defaultValue) as boolean;
      return val;
    } catch (err) {
      let error = err as BusinessError;
      console.error(`Failed to get preferences. Code:${error.code},message:${error.message}`);
      return defaultValue;
    }
  }

  static async delete(key: string): Promise<void> {
    try {
      const dataPreferences = await preferences.getPreferences(getContext(), PREFERENCES_NAME);
      await dataPreferences.delete(key);
      await dataPreferences.flush();
    } catch (err) {
      let error = err as BusinessError;
      console.error(`Failed to delete preferences. Code:${error.code},message:${error.message}`);
    }
  }
}