import { Icon } from "../Icon.jsx";

/**
 * 工作台的场景目录（左栏）。
 *
 * 这一栏承载三类**状态**，每一类都必须一眼可辨，因为它们决定用户下一步做什么：
 *
 * - **选中**：中性的实心 pill，比 hover 强一档并保持。刻意不用强调色条或边框——
 *   参考项目的结论是"选中就是 hover 那一档再加一档"，多加一种颜色反而更弱。
 * - **生成中**：脉冲骨架 + 真实的进度百分比。
 * - **失败**：真实原因 + 重试。绝不显示成空列表："没有内容"和"生成失败了"是
 *   两件完全不同的事。
 *
 * 三类共用同一个行高，切换课程时列不会重排。
 */
export default function WorkspaceSceneRail({
  stages = [],
  selectedStageId,
  onSelect,
  generating = false,
  progress = 0,
  failure = null,
  onRetry,
  loading = false,
  className = "",
}) {
  return <div className={`ow-rail ${className}`} data-testid="ow-scene-rail">
    <div className="ow-rail__head">
      <span className="ow-label">内容目录</span>
      <span className="ow-count">{stages.length}</span>
    </div>

    <div className="ow-rail__body">
      {loading ? <div className="ow-rail__skeleton" aria-busy="true">
        <span className="ow-skeleton" /><span className="ow-skeleton" /><span className="ow-skeleton" />
        <span className="ow-sr-only">正在读取内容目录</span>
      </div> : null}

      {/* 生成中：骨架卡片 + 真实进度。这是用户看得见的"正在生成"过程。 */}
      {!loading && generating ? <div className="ow-scene-item is-generating" role="status" data-testid="ow-scene-generating">
        <div className="ow-scene-item__thumb" aria-hidden="true">
          <span className="ow-scene-item__bar ow-scene-item__bar--title" />
          <span className="ow-scene-item__bar ow-scene-item__bar--line" />
          <span className="ow-scene-item__shimmer" />
        </div>
        <div className="ow-scene-item__copy">
          <strong>正在生成…</strong>
          <small>{Math.max(0, Math.min(100, Math.round(Number(progress) || 0)))}%</small>
        </div>
      </div> : null}

      {!loading && failure ? <div className="ow-scene-item is-failed" role="alert" data-testid="ow-scene-failed">
        <div className="ow-scene-item__thumb" aria-hidden="true"><Icon name="PhWarningCircle" size={18} /></div>
        <div className="ow-scene-item__copy">
          <strong>生成失败</strong>
          <small title={failure}>{failure}</small>
        </div>
        {onRetry ? <button type="button" className="ow-scene-item__retry" onClick={onRetry}>
          <Icon name="PhArrowClockwise" size={13} />重试
        </button> : null}
      </div> : null}

      {!loading && !generating && !failure && !stages.length ? <div className="ow-rail__empty" data-testid="ow-scene-empty">
        <Icon name="PhLayout" size={22} />
        <p>还没有课堂内容</p>
        <small>生成完成后，场景会按顺序出现在这里。</small>
      </div> : null}

      {!loading && !generating && !failure && stages.length ? <ol className="ow-scene-list">
        {stages.map((stage, index) => {
          const selected = stage.id === selectedStageId;
          return <li key={stage.id}>
            <button
              type="button"
              className={`ow-scene-item${selected ? " is-selected" : ""}`}
              aria-current={selected ? "true" : undefined}
              onClick={() => onSelect?.(stage.id)}
            >
              <span className="ow-scene-item__index" aria-hidden="true">{index + 1}</span>
              <span className="ow-scene-item__copy">
                <strong title={stage.title}>{stage.title}</strong>
                <small>{stage.dslVersion ? `DSL ${stage.dslVersion}` : "尚未写入内容"} · revision {stage.revision}</small>
              </span>
              {selected ? <Icon name="PhCaretRight" size={14} aria-hidden="true" /> : null}
            </button>
          </li>;
        })}
      </ol> : null}
    </div>
  </div>;
}
