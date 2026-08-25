/** Cookie data observable from ArkWeb; unavailable attributes remain undefined. */
export interface EduCookieDto {
  name: string;
  value: string;
  domain?: string;
  path?: string;
  secure?: boolean;
  http_only?: boolean;
  same_site?: string;
  expires?: number;
}
