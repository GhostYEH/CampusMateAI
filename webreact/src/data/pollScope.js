/**
 * "查看生成进度"的轮询作用域。
 *
 * 真实故障（课程详情页）：学生点"停止查看"时只 `clearTimeout` 了定时器，
 * 但**已经在途**的 `getInteractiveClassroomJob` 响应回来后，`isCurrent(myEpoch)`
 * 仍然是 true（课程没切、epoch 没变），于是它又 `schedulePoll(next, myEpoch)`
 * 把轮询重新点着了 —— 学生明确表示不看了，后台还在持续打后端。
 *
 * 正确做法：轮询有自己的 token。"停止查看"递增 token，任何在途响应在
 * **写状态之前**与**重新安排之前**都必须确认 token 仍然有效。
 */
export function createPollScope({ schedule = setTimeout, cancel = clearTimeout } = {}) {
  let token = 0;
  let handle = null;

  return {
    /** 当前 token（供测试/调试） */
    get token() {
      return token;
    },
    /** 是否有已安排的定时器 */
    get armed() {
      return handle !== null;
    },
    /** 出发时捕获 token；之后所有回写都用它校验。 */
    begin() {
      return token;
    },
    /** 该 token 是否仍然有效（有效才允许写状态 / 继续轮询）。 */
    isCurrent(myToken) {
      return myToken === token;
    },
    /** 安排一次轮询。返回是否真的安排了（token 失效时不安排）。 */
    arm(fn, ms, myToken = token) {
      if (myToken !== token) return false;
      handle = schedule(fn, ms);
      return true;
    },
    /** 定时器触发时清掉句柄（避免 stop 时重复清理）。 */
    disarm() {
      handle = null;
    },
    /** 停止查看：作废所有在途响应，并清掉已安排的定时器。 */
    stop() {
      token += 1;
      if (handle !== null) {
        cancel(handle);
        handle = null;
      }
    },
  };
}

export default createPollScope;
