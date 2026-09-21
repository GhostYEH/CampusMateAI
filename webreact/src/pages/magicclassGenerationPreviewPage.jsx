import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import * as api from "../data/api.js";
import { BackLink, Button, PageFrame, Panel } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import { itemsOf } from "../data/contracts.js";
import { describeFusionState } from "../features/magicclass/homeModel.js";
import { describeQuickAskFailure, pickReusableWorkspace, shouldBindWorkspace, workspaceHref } from "../features/magicclass/quickAskModel.js";
import { normalizeSelectedRoleIds, selectedRoles } from "../features/magicclass/roleModel.js";

const errorText = (error) => error?.message || "magic class 服务暂时不可用，请稍后重试。";

export default function MagicClassGenerationPreviewPage() {
  const { courseId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const location = useLocation();
  const prompt = searchParams.get("prompt")?.trim() || "";
  const mode = searchParams.get("mode") === "auto" ? "auto" : "preset";
  const roleIds = useMemo(() => normalizeSelectedRoleIds((searchParams.get("roles") || "").split(",").filter(Boolean)), [searchParams]);
  const roles = selectedRoles(roleIds);
  const [courseName, setCourseName] = useState("课程学习内容");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    Promise.all([api.getCourses(), api.getMagicClassFusionStatus()]).then(([coursePayload, fusionPayload]) => {
      if (!alive) return;
      const course = itemsOf(coursePayload).find((item) => String(item.id) === String(courseId));
      setCourseName(course?.name || course?.title || "课程学习内容");
      if (!shouldBindWorkspace(describeFusionState(fusionPayload))) setError("magic class 学习工作台暂时不可用，请返回课程页稍后重试。");
    }).catch((failure) => { if (alive) setError(errorText(failure)); });
    return () => { alive = false; };
  }, [courseId]);

  async function confirmGeneration() {
    if (!prompt || busy) return;
    setBusy(true);
    setError("");
    try {
      const payload = await api.listMagicClassWorkspaces(courseId, { limit: 1 });
      const reusable = pickReusableWorkspace(payload);
      const workspace = reusable || await api.createMagicClassWorkspace(courseId, {
        name: "magic class 学习课堂",
        description: "由课程学习内容生成，用于继续追问、编辑、播放与导出。",
        idempotencyKey: api.newIdempotencyKey(),
      });
      if (!workspace?.id) throw new Error("工作台创建结果缺少标识");
      navigate(workspaceHref(courseId, workspace.id, prompt, { mode, selectedRoleIds: roleIds }), {
        state: {
          magicclassWebSearch: searchParams.get("web") === "1" || Boolean(location.state?.magicclassWebSearch),
          magicclassAttachment: location.state?.magicclassAttachment || null,
        },
      });
    } catch (failure) {
      setError(describeQuickAskFailure(failure).message);
    } finally {
      setBusy(false);
    }
  }

  return <PageFrame className="magicclass-preview-page" eyebrow="magicclass / Generation Preview" title="生成预览" description="确认课堂主题与角色后，magic class 才会创建可编辑、可播放、可导出的学习工作台。" actions={<BackLink to="/courses">返回课程</BackLink>}>
    <div className="magicclass-preview">
      <Panel className="magicclass-preview__hero">
        <div className="magicclass-preview__brand"><span className="magicclass-brand-lockup__mark" aria-hidden="true"><Icon name="PhCube" size={25} weight="duotone" /></span><span><strong>magic class</strong><small>互动课堂生成预览</small></span></div>
        <span className="magicclass-preview__badge"><Icon name="PhCheckCircle" size={15} />确认后生成</span>
        <h2>{prompt || "未填写学习主题"}</h2>
        <p>课程：{courseName}</p>
      </Panel>
      <div className="magicclass-preview__grid">
        <Panel>
          <div className="magicclass-preview__section-head"><span><Icon name="PhUsersThree" size={18} />课堂角色</span><small>{mode === "auto" ? "自动安排" : `${roles.length} 位角色`}</small></div>
          <div className="magicclass-preview__roles">{mode === "auto" ? <div className="magicclass-preview__auto"><Icon name="PhShuffle" size={20} />根据课程主题自动安排角色</div> : roles.map((role) => <span className="magicclass-preview__role" key={role.id}><span style={{ background: role.color }}>{role.short}</span>{role.name}</span>)}</div>
        </Panel>
        <Panel>
          <div className="magicclass-preview__section-head"><span><Icon name="PhSparkle" size={18} />生成内容</span><small>原生工作台</small></div>
          <ul className="magicclass-preview__checks"><li><Icon name="PhCheck" size={15} />生成幻灯片与讲解内容</li><li><Icon name="PhCheck" size={15} />进入后可播放、可编辑并导出 PPTX</li><li><Icon name="PhCheck" size={15} />支持后续语音讲解与继续追问</li></ul>
        </Panel>
      </div>
      {error ? <div className="magicclass-preview__error" role="alert"><Icon name="PhWarningCircle" size={18} />{error}</div> : null}
      <div className="magicclass-preview__actions"><Button variant="secondary" onClick={() => navigate(-1)}>返回修改</Button><Button icon="PhSparkle" onClick={confirmGeneration} disabled={busy || !prompt}>{busy ? "正在准备课堂…" : error ? "重试并生成课堂" : "确认并生成课堂"}</Button></div>
    </div>
  </PageFrame>;
}
