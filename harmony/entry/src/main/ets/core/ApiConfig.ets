import { GeneratedApiEnv } from './GeneratedApiEnv';

/**
 * API Base URL 集中配置 (DEV / PROD 分离)。
 *
 * DEV_HOST 与 PROD_API_BASE_URL 由 hvigorfile.ts 在每次编译前从
 * harmony/api.local.properties (已被 .gitignore 忽略, 不纳入版本控制) 读取,
 * 并生成 ./GeneratedApiEnv.ets (同样被 .gitignore 忽略)。
 * 详见 harmony/api.local.properties.example。
 *
 * 开发环境 DEV_HOST:
 *   - 新 clone 无 local.properties 时, 默认 127.0.0.1 (DevEco Previewer / 后端同机可用)。
 *   - 真机 / 独立 Emulator 调试: 复制 api.local.properties.example -> api.local.properties,
 *     填 DEV_HOST=Windows 宿主机局域网 IPv4 (PowerShell: ipconfig 查看), 例 192.168.1.100。
 *   - HarmonyOS 真机的 127.0.0.1 指向手机自身, 无法访问电脑后端;
 *     Emulator 也没有 Android 的 10.0.2.2 映射。
 *
 * 生产环境 PROD_API_BASE_URL:
 *   - 留空表示尚未部署正式服务器, 将回退到 DEV_HOST 开发配置 (便于打包调试)。
 *   - 部署时在 api.local.properties 填正式 HTTPS API, 禁止 HTTP 明文, 禁止保留开发 IP。
 *
 * 业务页面不应直接写 Base URL, 统一从此处读取。
 * 本文件为 Git 跟踪源码, 开发者无需也不应修改本文件来配置自己的局域网 IP。
 */
export class ApiConfig {
  static readonly API_BASE_URL: string = ApiConfig.resolve();

  private static resolve(): string {
    const prod: string = GeneratedApiEnv.PROD_API_BASE_URL;
    if (prod && prod.length > 0) {
      return prod;
    }
    const host: string = GeneratedApiEnv.DEV_HOST || '127.0.0.1';
    return `http://${host}:8000/api/v1`;
  }
}
