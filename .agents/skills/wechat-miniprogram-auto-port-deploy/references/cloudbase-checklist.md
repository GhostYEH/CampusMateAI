# CloudBase Checklist

- Confirm `useCloudBase` and `cloudBaseEnvId` or `TCB_ENV_ID`/`CLOUD_BASE_ENV_ID`.
- Check `cloudbaserc.json`, `cloudbase.json`, or `tcb.json`.
- Confirm Mini Program account is bound to the CloudBase environment.
- Confirm `wx.cloud.init` exists and uses the correct `env`.
- Distinguish cloud functions from cloud run/container services.
- Confirm cloud function directory, usually `cloudfunctions/` or `functions/`.
- Confirm cloud run service name, endpoint, and access method.
- Review database permissions and security rules.
- Review file storage permissions and privacy impact.
- Do not assume local developer has environment admin permission.
- For CloudBase Framework Mini Program plugin, generate config with `appid`, `privateKeyPath` or runtime `privateKey`, `localPath`, `deployMode`, `qrcodeOutputPath`, `commands.install`, and `commands.build`.
- In CI, read CloudBase credentials from secrets, not repository files.
