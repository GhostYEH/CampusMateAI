import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as api from "../data/api.js";
import { Button, PageFrame } from "../components/Primitives.jsx";
import { Icon } from "../components/Icon.jsx";
import { itemsOf } from "../data/contracts.js";
import { describeFusionState } from "../features/openmaic/homeModel.js";
import {
  CLASSROOM_GENERATION_STEPS,
  buildClassroomPrompt,
  classroomEntryIdempotencyKey,
  describeCourseReadiness,
  describeEntryFailure,
  enterClassroomHref,
  resolveGenerationPhase,
  stageGenerationIdempotencyKey,
} from "../features/openmaic/enterClassroomModel.js";
import { workspaceHref } from "../features/openmaic/quickAskModel.js";
import { normalizeStageList, normalizeWorkspaceList } from "../features/openmaic/workspaceModel.js";

/**
 * 「进入课堂」直达页 —— 用户按下按钮之后发生的一切。
 *
 * 这一页取代了原来的「角色 → 模式 → 预览 → 确认」四步。它做四件事，顺序不能乱：
 *
 * 1. 读真实课程事实（只读，不依赖受管服务），据此构造默认主题；
 * 2. **复用或创建**该课程的工作台，用确定性的幂等键，所以双击/刷新只会得到一个；
 * 3. 复用或创建首个课堂内容，同样用确定性键，已经有 stage 时只恢复不重生成；
 * 4. 轮询生成进度，完成后进入工作台。
 *
 * 两个反复出现的缺陷在这里被显式挡住：
 *
 * - **整页错误替换工作台**：所有失败都收敛到页面内的一个区块，`PageFrame` 始终在，
 *   课程名与"重试/手动创建"始终可点。
 * - **把不可用说成已完成**：只有 `completed` 才渲染完成态；其余一律照实说明原因。
 *
 * 代次（`epoch`）守卫每一次异步回写：切课程或卸载之后，迟到的响应不会写进新课程。
 */
export default function OpenMAICClassroomEntryPage() {
  const { courseId } = useParams();
  const navigate = useNavigate();

  const [course, setCourse] = useState(null);
  const [online, setOnline] = useState(false);
  const [workspace, setWorkspace] = useState(null);
  const [stages, setStages] = useState([]);
  const [job, setJob] = useState(null);
  const [phase, setPhase] = useState(null);
  const [failure, setFailure] = useState(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(true);
  const [entered, setEntered] = useState(false);

  // 代次与轮询句柄。切课程或**真实卸载**必须把它 +1，否则旧课程的响应会写进新
  // 课程的页面。
  const epoch = useRef(0);
  const timer = useRef(null);
  /**
   * 正在飞行的那一次进入，**带课程归属**。
   *
   * 记录的是 `{ courseId, promise }`，而不是"跑过没有"的布尔值，也不是裸 Promise。
   * 三点都是必须的：
   *
   * 1. 存 Promise 而非布尔值：StrictMode 会"挂载 → 模拟卸载 → 再挂载"，两次
   *    effect 都会调 enter()。用布尔值挡住第二次，第一次的结果又已被模拟卸载作废，
   *    页面就永久停在等待态（真实复现过）。共享同一个在飞 Promise 则第二次**复用它**
   *    而不是重跑，既不会重复请求、也不会互相作废。
   * 2. 带 courseId 归属：切换课程时，B 的 enter() **绝不能**复用 A 的在飞 Promise。
   *    否则 B 会直接 return，而 A 随后又被作废，于是两边都没人推进，B 永久停在
   *    "正在确认受管服务状态…"（真实复现过）。只有同一门课程才允许复用。
   * 3. 由单一 effect 负责"作废旧课程 → 立即启动新课程"：如果作废与启动分散在两个
   *    effect 里，React 按声明顺序执行会让"启动"先于"作废"跑，B 看到 A 的 Promise
   *    后 return，之后没有任何东西再启动 B。顺序依赖本身就是 bug 的来源。
   */
  const inFlight = useRef(null);

  const goToWorkspace = useCallback((workspaceId, prompt) => {
    // `mode=playback` 让工作台一进来就是学习态。用户点的是「进入课堂」，
    // 落到编辑器布局再让他自己找「开始学习」是把入口的语义丢在了半路。
    navigate(workspaceHref(courseId, workspaceId, prompt, { mode: "playback" }), { replace: true });
  }, [courseId, navigate]);
  /**
   * 轮询一次生成任务。
   *
   * 终止态一律回到 `loadWorkspace`：即使失败也要重新读一次，因为服务端可能在
   * 失败前已经落库了部分内容，界面必须以服务端为准而不是以本地推测为准。
   */
  const poll = useCallback(async (jobId, workspaceId, prompt) => {
    const mine = epoch.current;
    try {
      const current = await api.getOpenMAICJob(courseId, jobId);
      if (mine !== epoch.current) return;
      setJob(current);
      setPhase(resolveGenerationPhase(current));
      if (["queued", "running"].includes(current.status)) {
        timer.current = window.setTimeout(() => void poll(jobId, workspaceId, prompt), 800);
        return;
      }
      if (current.status === "completed") {
        setNotice("课堂内容已生成，正在进入工作台。");
        goToWorkspace(workspaceId, prompt);
        return;
      }
      // failed / cancelled：不跳转，留在本页给出真实原因与可行动作。
      setBusy(false);
      setFailure(describeEntryFailure({ response: { status: 200, data: current } }));
    } catch (error) {
      if (mine !== epoch.current) return;
      setBusy(false);
      setFailure(describeEntryFailure(error));
    }
  }, [courseId, goToWorkspace]);

  /**
   * 进入课堂的完整流程。
   *
   * 关键在于**每一步都先问服务端"已经有了吗"**，而不是先建再看。这正是双击与
   * 刷新不产生重复内容的实现方式——幂等键是第二道保险，先查是第一道。
   *
   * 之所以要在"先查后建"之外再加确定性幂等键：StrictMode 下这一次流程可能被
   * 并发触发两次（两个标签页、双击、或开发期的双挂载）。先查在两次请求交错时
   * 会双双查空，于是双双走到创建；此时**只有**服务端的确定性键能保证最终仍然
   * 只有一个工作台与一个首 stage。
   */
  const enter = useCallback(async () => {
    // 只复用**同一门课程**的在飞流程：StrictMode 的第二次挂载因此不会重跑一遍，
    // 而切换课程时 B 不会误复用 A 的 Promise（那样 B 会被直接 return 掉）。
    if (inFlight.current && inFlight.current.courseId === courseId) {
      return inFlight.current.promise;
    }

    const mine = ++epoch.current;
    const run = (async () => {
      setBusy(true);
      setFailure(null);
      setNotice("");

      let prompt = "";
      try {        // 1) 真实课程事实（只读，不走受管服务）
        const [coursePayload, contextPayload] = await Promise.all([
          api.getCourses(),
          api.getOpenMAICCourseContext(courseId).catch(() => null),
        ]);
        if (mine !== epoch.current) return;
        const found = itemsOf(coursePayload).find((item) => String(item.id) === String(courseId)) || null;
        // 课程基本信息以路由上的真实课程为准；context 作为补充来源。
        const facts = {
          name: found?.name || found?.title || contextPayload?.name || "",
          code: found?.code || contextPayload?.code || "",
          semester: found?.semester || contextPayload?.semester || "",
          description: found?.description || contextPayload?.description || "",
          chapters: contextPayload?.chapters || [],
          knowledgePoints: contextPayload?.knowledge_points || [],
          materials: contextPayload?.materials || [],
          warnings: contextPayload?.warnings || [],
        };
        const readiness = describeCourseReadiness(facts);
        setCourse(found || (facts.name ? { name: facts.name } : null));
        // 默认主题纳入已授权的真实课程信息与已同步的章节/资料标题。
        prompt = buildClassroomPrompt(facts);
        if (!readiness.synced) setNotice(readiness.notice);

        // 2) 受管服务是否可用。不可用就**不进入**，并说清原因。
        const fusion = await api.getOpenMAICFusionStatus().catch(() => null);
        if (mine !== epoch.current) return;
        const fusionView = describeFusionState(fusion);
        const canEnter = fusionView.state === "ready" && fusionView.canCreateWorkspace;
        setOnline(canEnter);
        if (!canEnter) {
          throw {
            response: {
              status: 503,
              data: {
                code: "OPENMAIC_FUSION_UNAVAILABLE",
                message: fusionView.detail || "受管 OpenMAIC 学习工作台当前不可用。",
                details: { reason: String(fusion?.reason || "") },
              },
            },
          };
        }

        // 3) 复用已有工作台，否则用确定性键创建。
        //    先查后建：双击时两次调用都会走到同一个已有工作台；若两次查询交错
        //    同时落空，服务端的确定性键保证最终仍只有一个。
        const listed = await api.listOpenMAICWorkspaces(courseId, { limit: 1 });
        if (mine !== epoch.current) return;
        let target = normalizeWorkspaceList(listed)[0] || null;
        if (!target) {
          const created = await api.createOpenMAICWorkspace(courseId, {
            name: facts.name ? `${facts.name} · 学习课堂` : "OpenMAIC 学习课堂",
            description: "由课程真实知识点生成，可继续编辑、播放与导出。",
            // 确定性键：同课程恒定，双击/重试不会建出第二个工作台。
            idempotencyKey: classroomEntryIdempotencyKey(courseId),
          });
          if (mine !== epoch.current) return;
          target = normalizeWorkspaceList({ items: [created] })[0] || null;
        }
        if (!target?.id) throw new Error("工作台创建结果缺少标识");
        setWorkspace(target);

        // 4) 已有内容 → 只恢复，不重复生成。这是"刷新不能重复生成"的实现。
        const stagePayload = await api.listOpenMAICStages(courseId, target.id, { limit: 50 });
        if (mine !== epoch.current) return;
        const existing = normalizeStageList(stagePayload);
        setStages(existing);
        if (existing.length) {
          setNotice("已恢复该课程已有的课堂内容。");
          goToWorkspace(target.id, "");
          return;
        }

        // 5) 还没有内容：立即开始生成首个课堂内容。
        const key = stageGenerationIdempotencyKey(courseId, prompt);
        const result = await api.generateOpenMAICStage(courseId, target.id, {
          mode: "slide",
          prompt,
          idempotencyKey: key,
        });
        if (mine !== epoch.current) return;
        const nextJob = result?.job || null;
        setJob(nextJob);
        setPhase(resolveGenerationPhase(nextJob));
        if (!nextJob?.id) {
          // 没有任务号却返回成功：当作已就绪，直接进入工作台（仍以服务端 stage 为准）。
          const after = normalizeStageList(await api.listOpenMAICStages(courseId, target.id, { limit: 50 }));
          if (mine !== epoch.current) return;
          if (after.length) { goToWorkspace(target.id, ""); return; }
          throw new Error("受管服务未返回生成任务");
        }
        if (nextJob.status === "completed") { goToWorkspace(target.id, ""); return; }
        void poll(nextJob.id, target.id, "");
      } catch (error) {
        if (mine !== epoch.current) return;
        setBusy(false);
        setFailure(describeEntryFailure(error));
      } finally {
        // 无论成功失败都释放"在飞"标记，重试才能重新开始。
        // 只释放属于自己的那一次，避免把后来者的标记清掉。
        if (inFlight.current && inFlight.current.promise === run) inFlight.current = null;
      }
    })();

    inFlight.current = { courseId, promise: run };
    return run;
  }, [courseId, goToWorkspace, poll]);

  /**
   * 进入流程的唯一启动点，同时负责课程切换时的"作废旧课程 → 立即启动新课程"。
   *
   * 把两件事放进**同一个 effect** 是刻意的。此前拆成两个 effect（一个启动、一个在
   * 课程变化时清理）时，React 按声明顺序执行会让启动先跑：B 的 enter() 看到 A 的在飞
   * Promise 就 return，紧接着清理 effect 把它清掉，却**没有**再启动 B，于是 B 永久
   * 停在等待态。现在顺序不再重要——先作废旧的，再无条件启动新的。
   *
   * StrictMode 的模拟卸载不会走到这里（依赖没变，effect 不重跑）；它以同一个
   * courseId 重新挂载时，enter() 会复用同一门课的在飞 Promise，既不重复请求也不会
   * 自我作废。
   */
  useEffect(() => {
    // 1) 先作废旧课程：递增代次让 A 的迟到响应不再写 state / 建 workspace / 排轮询，
    //    并停掉 A 可能还挂着的轮询计时器。
    epoch.current += 1;
    if (timer.current) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
    // 只有属于别的课程的在飞标记才作废；同一门课的（StrictMode 复挂载）必须保留，
    // 否则第二次挂载会重跑一遍整条链路。
    if (inFlight.current && inFlight.current.courseId !== courseId) {
      inFlight.current = null;
    }
    // 2) 再立即启动本课程，不依赖任何后续 effect 再次触发。
    void enter();
  }, [courseId, enter]);

  /**
   * 真实卸载：让在途请求与轮询的迟到结果不再产生任何副作用。
   *
   * 递增代次后，所有 `mine !== epoch.current` 检查都会生效——迟到的响应不会写 state、
   * 不会创建 workspace/stage、也不会重新安排 poll。同时清掉在飞标记与计时器，使重新
   * 挂载（或切回本课程）必须重新开始，而不是复用已经作废的流程。
   */
  useEffect(() => () => {
    epoch.current += 1;
    inFlight.current = null;
    if (timer.current) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  /** 重试：直接重跑整个流程，仍然复用同一个确定性键。 */
  const retry = useCallback(() => { void enter(); }, [enter]);

  /**
   * 手动创建：跳过生成，只保证有一个可编辑的工作台。
   * 这是生成失败时唯一还走得通的路，所以它必须在失败态里一直可点。
   */
  const createManually = useCallback(async () => {
    const mine = ++epoch.current;
    setBusy(true);
    setFailure(null);
    try {
      const listed = await api.listOpenMAICWorkspaces(courseId, { limit: 1 });
      if (mine !== epoch.current) return;
      let target = normalizeWorkspaceList(listed)[0] || null;
      if (!target) {
        const created = await api.createOpenMAICWorkspace(courseId, {
          name: course?.name ? `${course.name} · 学习课堂` : "OpenMAIC 学习课堂",
          description: "手动创建的学习课堂。",
          idempotencyKey: classroomEntryIdempotencyKey(courseId),
        });
        if (mine !== epoch.current) return;
        target = normalizeWorkspaceList({ items: [created] })[0] || null;
      }
      if (!target?.id) throw new Error("工作台创建结果缺少标识");
      setEntered(true);
      goToWorkspace(target.id, "");
    } catch (error) {
      if (mine !== epoch.current) return;
      setBusy(false);
      setFailure(describeEntryFailure(error));
    }
  }, [courseId, course, goToWorkspace]);

  const title = course?.name || course?.title || "进入课堂";
  const currentPhase = phase || resolveGenerationPhase(job);
  const steps = useMemo(() => CLASSROOM_GENERATION_STEPS, []);

  return <PageFrame
    className="openmaic-entry-page"
    eyebrow="OpenMAIC / Classroom"
    title={title}
    description="正在为你准备这堂课的互动课堂。"
    actions={<Button variant="secondary" icon="PhArrowLeft" onClick={() => navigate("/courses")}>返回课程</Button>}
  >
    <div className="openmaic-entry">
      {/* 生成过程。这是用户看得见的"生成课程大纲 / 构建学习路径"，不是装饰。 */}
      {!failure ? <section className="openmaic-entry__progress" aria-live="polite" aria-busy={busy}>
        <div className="openmaic-entry__head">
          <span className="openmaic-entry__mark" aria-hidden="true"><Icon name="PhCube" size={26} weight="duotone" /></span>
          <div>
            <strong>{"magic'class"} 正在准备课堂</strong>
            <small>{currentPhase.title}{currentPhase.description ? ` · ${currentPhase.description}` : ""}</small>
          </div>
        </div>

        {/* 阶段点阵：已过 / 当前 / 未来三态，与原项目一致。 */}
        <ol className="openmaic-entry__steps">
          {steps.map((step, index) => {
            const state = currentPhase.done || index < currentPhase.index
              ? "is-done"
              : index === currentPhase.index ? "is-current" : "is-next";
            return <li key={step.key} className={`openmaic-entry__step ${state}`}>
              <span className="openmaic-entry__dot" aria-hidden="true">
                {state === "is-done" ? <Icon name="PhCheck" size={12} weight="bold" /> : null}
              </span>
              <span className="openmaic-entry__step-copy">
                <strong>{step.title}</strong>
                <small>{state === "is-current" ? step.description : state === "is-done" ? "已完成" : "等待中"}</small>
              </span>
            </li>;
          })}
        </ol>

        <div className="openmaic-entry__bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={currentPhase.percent} aria-label="生成进度">
          <span style={{ width: `${currentPhase.percent}%` }} />
        </div>
        <p className="openmaic-entry__hint" role="status">
          {currentPhase.done ? "生成完成。" : `进度 ${currentPhase.percent}%`}
          {notice ? ` · ${notice}` : ""}
        </p>
      </section> : null}

      {/* 失败：局部错误，绝不替换整页；始终给出可执行的下一步。 */}
      {failure ? <section className="openmaic-entry__error" role="alert">
        <Icon name="PhWarningCircle" size={22} />
        <div>
          <strong>{failure.message}</strong>
          <small>
            {failure.canRetry
              ? "可以立即重试；重试会沿用同一个工作台，不会产生重复内容。"
              : "这个问题重试通常无效，请修复配置后返回课程页重进。"}
          </small>
          <div className="openmaic-entry__error-actions">
            {failure.canRetry ? <Button icon="PhArrowClockwise" onClick={retry} disabled={busy}>{busy ? "正在重试…" : "重试生成"}</Button> : null}
            {failure.canCreateManually ? <Button variant="secondary" icon="PhSquaresFour" onClick={createManually} disabled={busy}>手动创建工作台</Button> : null}
            <Button variant="quiet" onClick={() => navigate("/courses")}>返回课程</Button>
          </div>
        </div>
      </section> : null}

      {/* 工作台已经就绪但还没跳转时的兜底入口，保证用户永远有一条路可走。 */}
      {workspace?.id && !failure ? <p className="openmaic-entry__link">
        {entered ? "正在打开工作台…" : <>工作台已就绪：<button type="button" className="openmaic-entry__jump" onClick={() => goToWorkspace(workspace.id, "")}>直接进入「{workspace.name}」</button></>}
      </p> : null}

      {!online && !failure && !workspace ? <p className="openmaic-entry__hint">正在确认受管服务状态…</p> : null}
    </div>
  </PageFrame>;
}
