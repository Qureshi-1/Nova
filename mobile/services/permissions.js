import { PermissionsAndroid, Platform } from "react-native";
import * as IntentLauncher from "expo-intent-launcher";
import Constants from "expo-constants";

export async function ensurePermissions(onGuideStorage) {
  const granted = [];
  if (Platform.OS !== "android") return granted;
  try {
    const mic = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.RECORD_AUDIO
    );
    if (mic === PermissionsAndroid.RESULTS.GRANTED) granted.push("RECORD_AUDIO");
    if (Platform.Version >= 33) {
      const notif = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS
      );
      if (notif === PermissionsAndroid.RESULTS.GRANTED) granted.push("POST_NOTIFICATIONS");
    }
    if (Platform.Version >= 30) {
      const storage = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.MANAGE_EXTERNAL_STORAGE
      );
      if (storage === PermissionsAndroid.RESULTS.GRANTED) {
        granted.push("MANAGE_EXTERNAL_STORAGE");
      } else {
        onGuideStorage && onGuideStorage();
        try {
          await IntentLauncher.startActivityAsync(
            "android.settings.MANAGE_APP_ALL_FILES_ACCESS_PERMISSION",
            { data: "package:" + Constants.expoConfig?.android?.package }
          );
        } catch (error) {
          try {
            await IntentLauncher.startActivityAsync(
              "android.settings.MANAGE_APPLICATIONS_SETTINGS"
            );
          } catch (error2) {}
        }
      }
    }
  } catch (error) {}
  return granted;
}

export async function hasStoragePermission() {
  if (Platform.OS !== "android" || Platform.Version < 30) return true;
  try {
    return await PermissionsAndroid.check(
      PermissionsAndroid.PERMISSIONS.MANAGE_EXTERNAL_STORAGE
    );
  } catch (error) {
    return false;
  }
}
