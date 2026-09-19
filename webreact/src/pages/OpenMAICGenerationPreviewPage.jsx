import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import * as api from "../data/api.js";
import { BackLink, Button, PageFrame, Panel } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import { itemsOf } from "../data/contracts.js";
import { describeFusionState } from "../features/openmaic/homeModel.js";
import { describeQuickAskFailure, pickReusableWorkspace, shouldBindWorkspace, workspaceHref } from "../features/openmaic/quickAskModel.js";
import { normalizeSelectedRoleIds, selectedRoles } from "../features/openmaic/roleModel.js";

const errorText = (error) => error?.message || "OpenMAIC 服务暂时不可用，请稍后重试。";

export default function OpenMAICGenerationPreviewPage() {
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
    Promise.all([api.getCourses(), api.getOpenMAICFusionStatus()]).then(([coursePayload, fusionPayload]) => {
      if (!alive) return;
      const course = itemsOf(coursePayload).find((item) => String(item.id) === String(courseId));
      setCourseName(course?.name || course?.title || "课程学习内容");
      if (!shouldBindWorkspace(describeFusionState(fusionPayload))) setError("OpenMAIC 学习工作台暂时不可用，请返回课程页稍后重试。");
    }).catch((failure) => { if (alive) setError(errorText(failure)); });
    return () => { alive = false; };
  }, [courseId]);

  async function confirmGeneration() {
    if (!prompt || busy) return;
    setBusy(true);
    setError("");
    try {
      const payload = await api.listOpenMAICWorkspaces(courseId, { limit: 1 });
      const reusable = pickReusableWorkspace(payload);
      const workspace = reusable || await api.createOpenMAICWorkspace(courseId, {
        name: "OpenMAIC 学习课堂",
        description: "由课程学习内容生成，用于继续追问、编辑、播放与导出。",
        idempotencyKey: api.newIdempotencyKey(),
      });
      if (!workspace?.id) throw new Error("工作台创建结果缺少标识");
      navigate(workspaceHref(courseId, workspace.id, prompt, { mode, selectedRoleIds: roleIds }), {
        state: {
          openmaicWebSearch: searchParams.get("web") === "1" || Boolean(location.state?.openmaicWebSearch),
          openmaicAttachment: location.state?.openmaicAttachment || null,
        },
      });
    } catch (failure) {
      setError(describeQuickAskFailure(failure).message);
    } finally {
      setBusy(false);
    }
  }

  return <PageFrame className="openmaic-preview-page" eyebrow="OpenMAIC / Generation Preview" title="生成预览" description="确认课堂主题与角色后，OpenMAIC 才会创建可编辑、可播放、可导出的学习工作台。" actions={<BackLink to="/courses">返回课程</BackLink>}>
    <div className="openmaic-preview">
      <Panel className="openmaic-preview__hero">
        <div className="openmaic-preview__brand"><span className="openmaic-brand-lockup__mark" aria-hidden="true"><Icon name="PhCube" size={25} weight="duotone" /></span><span><strong>OpenMAIC</strong><small>互动课堂生成预览</small></span></div>
        <span className="openmaic-preview__badge"><Icon name="PhCheckCircle" size={15} />确认后生成</span>
        <h2>{prompt || "未填写学习主题"}</h2>
        <p>课程：{courseName}</p>
      </Panel>
      <div className="openmaic-preview__grid">
        <Panel>
          <div className="openmaic-preview__section-head"><span><Icon name="PhUsersThree" size={18} />课堂角色</span><small>{mode === "auto" ? "自动安排" : `${roles.length} 位角色`}</small></div>
          <div className="openmaic-preview__roles">{mode === "auto" ? <div className="openmaic-preview__auto"><Icon name="PhShuffle" size={20} />根据课程主题自动安排角色</div> : roles.map((role) => <span className="openmaic-preview__role" key={role.id}><span style={{ background: role.color }}>{role.short}</span>{role.name}</span>)}</div>
        </Panel>
        <Panel>
          <div className="openmaic-preview__section-head"><span><Icon name="PhSparkle" size={18} />生成内容</span><small>原生工作台</small></div>
          <ul className="openmaic-preview__checks"><li><Icon name="PhCheck" size={15} />生成幻灯片与讲解内容</li><li><Icon name="PhCheck" size={15} />进入后可播放、可编辑并导出 PPTX</li><li><Icon name="PhCheck" size={15} />支持后续语音讲解与继续追问</li></ul>
        </Panel>
      </div>
      {error ? <div className="openmaic-preview__error" role="alert"><Icon name="PhWarningCircle" size={18} />{error}</div> : null}
      <div className="openmaic-preview__actions"><Button variant="secondary" onClick={() => navigate(-1)}>返回修改</Button><Button icon="PhSparkle" onClick={confirmGeneration} disabled={busy || !prompt}>{busy ? "正在准备课堂…" : error ? "重试并生成课堂" : "确认并生成课堂"}</Button></div>
    </div>
  </PageFrame>;
}
