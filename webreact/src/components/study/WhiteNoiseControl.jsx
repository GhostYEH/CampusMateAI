import { ElasticSlider } from "./ElasticSlider.jsx";
import { Icon } from "../Icon.jsx";

export function WhiteNoiseControl({ enabled, volume, onToggle, onVolumeChange }) {
  const muted = !enabled || volume === 0;
  return <div className={`white-noise-control ${enabled ? "is-playing" : "is-muted"}`}>
    <button
      type="button"
      className="white-noise-control__toggle"
      aria-label={enabled ? "关闭白噪音" : "开启白噪音"}
      aria-pressed={enabled}
      onClick={onToggle}
    >
      <span className="white-noise-control__orb"><Icon name={muted ? "PhSpeakerSimpleX" : "PhWaveform"} size={19} weight={enabled ? "fill" : "regular"} /></span>
    </button>
    <div className="white-noise-control__copy">
      <strong>环境白噪音</strong>
      <span>{enabled ? (volume === 0 ? "已静音 · 点击恢复" : "柔和播放中") : "点击左侧开始播放"}</span>
    </div>
    <div className="white-noise-control__slider">
      <ElasticSlider value={volume} onChange={onVolumeChange} min={0} max={100} step={5} />
    </div>
    <span className="white-noise-control__value" aria-live="polite">{volume}%</span>
  </div>;
}
