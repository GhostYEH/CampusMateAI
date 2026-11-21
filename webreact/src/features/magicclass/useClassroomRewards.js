import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  emptyRewards,
  gradeScene,
  levelOf,
  readRewards,
  rewardsKey,
  sceneMap,
  visitScene,
  writeRewards,
} from "./rewardsModel.js";

/**
 * 把奖励模型接到课堂：负责读写 localStorage、把"首次访问/首次交卷"落盘，
 * 并把本次新解锁的成就交给界面提示。
 *
 * 状态用 ref 与 state 两份：连续翻页时同一帧可能触发多次结算，只读 state
 * 会拿到过期快照，导致 XP 少加或重复加。所有写入都基于 ref 的最新值。
 */
export function useClassroomRewards({ courseId, workspaceId, stageId, totalScenes = 0, scenes = [], index = 0 }) {
  const key = useMemo(
    () => rewardsKey({ courseId, workspaceId, stageId }),
    [courseId, workspaceId, stageId],
  );
  const storage = typeof window !== "undefined" ? window.localStorage : null;
  const [state, setState] = useState(() => readRewards(storage, key));
  const stateRef = useRef(state);
  const [unlocked, setUnlocked] = useState([]);

  useEffect(() => {
    const loaded = readRewards(storage, key);
    stateRef.current = loaded;
    setState(loaded);
    setUnlocked([]);
  }, [key, storage]);

  const commit = useCallback((next) => {
    stateRef.current = next;
    setState(next);
    writeRewards(storage, key, next);
  }, [key, storage]);

  const visit = useCallback((sceneId) => {
    const result = visitScene(stateRef.current, sceneId, { totalScenes });
    if (result.state === stateRef.current) return;
    commit(result.state);
    if (result.unlocked.length) setUnlocked((current) => [...current, ...result.unlocked]);
  }, [commit, totalScenes]);

  const grade = useCallback((payload) => {
    if (!payload?.sceneId) return;
    const result = gradeScene(stateRef.current, payload, { totalScenes });
    if (result.state === stateRef.current) return;
    commit(result.state);
    if (result.unlocked.length) setUnlocked((current) => [...current, ...result.unlocked]);
  }, [commit, totalScenes]);

  const dismissUnlock = useCallback((id) => {
    setUnlocked((current) => current.filter((item) => item !== id));
  }, []);

  const level = useMemo(() => levelOf(state.xp), [state.xp]);
  const map = useMemo(() => sceneMap(state, scenes, index), [state, scenes, index]);

  return {
    key,
    state: state || emptyRewards(),
    level,
    combo: state.combo,
    bestCombo: state.bestCombo,
    achievements: state.achievements,
    map,
    unlocked,
    visit,
    grade,
    dismissUnlock,
  };
}
