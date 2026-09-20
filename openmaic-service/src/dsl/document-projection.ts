/**
 * 读取时的文档投影：把历史舞台文档补成当前渲染器认得的形态。
 *
 * 挂在这里而不是散在各处，是因为**读取咽喉只有一个**——编辑、播放、导出、归档、
 * 渲染全都经过 `WorkspaceRepository.getStage`。补一次就覆盖全部调用方；分散到各
 * 路由迟早会漏掉某一条（归档导出带上旧内容、播放器判定不到元素之类）。
 *
 * 目前两件事：
 * 1. 幻灯片画布缺元素 → 合成真实画布（见 `slide-canvas.ts`）；
 * 2. PBL 场景缺 `projectV2` → 合成项目（见 `pbl-project.ts`）。
 *
 * 两条都遵守同一组边界：**只补确实缺失的**、**无改动返回同一引用**、**不注入
 * 时间戳**（否则读一次就"变"一次，幂等与"没变就不重写"都失效）。
 */
import { upgradeLegacySlideCanvases } from './slide-canvas.ts';
import { upgradeLegacyPblProjects } from './pbl-project.ts';

export function projectStoredDocument(document: unknown): unknown {
  const withSlides = upgradeLegacySlideCanvases(document);
  const withPbl = upgradeLegacyPblProjects(withSlides);
  // 任一环节改过就必须返回新对象；都没改时 `withPbl === document`，调用方据此
  // 跳过序列化，保证"没有改动"时逐字节返回存储原样。
  return withPbl;
}
