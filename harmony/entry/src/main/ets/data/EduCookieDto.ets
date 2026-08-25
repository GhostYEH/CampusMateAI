/** Cookie data observable from ArkWeb; unavailable attributes remain undefined. */
export interface EduCookieDto {
  name: string;
  value: string;
  domain?: string;
  source_url?: string;
  host_only?: boolean;
  path?: string;
  secure?: boolean;
  http_only?: boolean;
  same_site?: string;
  expires?: number;
}
