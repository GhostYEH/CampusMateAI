/**
 * API Base URL 集中配置。
 *
 * Debug:
 *   - DEV_HOST 默认 127.0.0.1,适合 DevEco Previewer(与后端同机)。
 *   - 独立 DevEco Emulator 必须把 DEV_HOST 改为 Windows 宿主机当前局域网 IPv4
 *     (PowerShell: ipconfig 查看 IPv4 地址),例如 192.168.1.100。
 *   - HarmonyOS Emulator 没有 Android 的 10.0.2.2 宿主机映射,
 *     127.0.0.1 在独立模拟器中指向模拟器自身而非 Windows。
 *   - 不要把具体局域网 IP 提交到仓库;DEV_HOST 仅作为本机开发占位。
 *   - 当前值 192.168.1.14 为本机临时调试地址,DHCP 变化后需重新 ipconfig 查询。
 *
 * Release:
 *   - 必须把 IS_DEBUG 改为 false,或直接使用 RELEASE_API_BASE_URL。
 *   - 必须使用正式 HTTPS API,禁止 HTTP 明文,禁止保留开发 IP。
 *
 * 业务页面不应直接写 Base URL,统一从此处读取。
 */
const DEV_HOST: string = '192.168.1.14';
const DEV_API_BASE_URL: string = `http://${DEV_HOST}:8000/api/v1`;
const RELEASE_API_BASE_URL: string = 'https://api.campusmate.example.com/api/v1';
const IS_DEBUG: boolean = true;

export class ApiConfig {
  static readonly API_BASE_URL: string =
    IS_DEBUG ? DEV_API_BASE_URL : RELEASE_API_BASE_URL;
}
