package com.example.campusai.ui.strings

/**
 * 核心模块的中文文案集中管理。
 * 页面中不再散落硬编码字符串。
 */
object CampusStrings {

    object Common {
        const val BACK = "返回"
        const val CONFIRM = "确认"
        const val CANCEL = "取消"
        const val SAVE = "保存"
        const val DELETE = "删除"
        const val SUBMIT = "提交"
        const val LOADING = "加载中…"
        const val RETRY = "重试"
        const val ALL = "全部"
        const val OPTIONAL = "选填"
    }

    object Exams {
        const val TITLE = "考试安排"
        const val SUBTITLE = "本地记录，接入教务系统后可自动同步"
        const val ADD = "新增考试"
        const val EDIT = "编辑考试"
        const val FILTER_ALL = "全部"
        const val FILTER_UPCOMING = "未开始"
        const val FILTER_ENDED = "已结束"
        const val NEAREST_TITLE = "最近一场考试"
        const val NO_UPCOMING = "近期没有即将到来的考试"
        const val EMPTY = "暂无考试安排，点击右上角添加"
        const val LOAD_ERROR = "考试数据加载失败，请重试"
        const val DAYS_LEFT = "天后开考"
        const val TODAY = "今天开考"
        const val OVERVIEW_TODAY = "今天"
        const val OVERVIEW_COUNT = "本学期还有 %d 场考试"
        const val OVERVIEW_EMPTY_HINT = "添加考试后，这里会为你提示最近一场"
        const val SCHEDULE_TITLE = "考试日程"
        const val SCHEDULE_COUNT = "%d 场"
        const val SEAT_PREFIX = "座位 "
        const val FIELD_COURSE = "课程名称"
        const val FIELD_DATE = "考试日期"
        const val FIELD_START = "开始时间"
        const val FIELD_END = "结束时间"
        const val FIELD_LOCATION = "考试地点"
        const val FIELD_SEAT = "座位号"
        const val FIELD_TYPE = "考试类型"
        const val REMINDER = "考前提醒"
        const val REMINDER_ON = "已开启，考前 1 天提醒你"
        const val REMINDER_OFF = "已关闭"
        const val DELETE_TITLE = "删除考试"
        const val DELETE_MESSAGE = "删除后无法恢复，确定删除这场考试吗？"
        const val DETAIL_TITLE = "考试详情"
        const val ERROR_REQUIRED = "请完整填写课程、日期、时间与地点"
        const val ERROR_TIME_ORDER = "结束时间需要晚于开始时间"
        const val TYPES = "期末考试,期中考试,随堂测验,补考"
    }

    object Focus {
        const val TITLE = "专注自习"
        const val SUBTITLE = "番茄钟计时，状态本地保存，退出不丢失"
        const val MODE_FOCUS = "专注 25 分钟"
        const val MODE_SHORT = "短休息 5 分钟"
        const val MODE_LONG = "长休息 15 分钟"
        const val START = "开始"
        const val PAUSE = "暂停"
        const val RESUME = "继续"
        const val END = "结束"
        const val END_TITLE = "结束本次计时"
        const val END_MESSAGE = "本次计时还未完成，提前结束将按实际时长记录，确定结束吗？"
        const val STATUS_RUNNING = "专注中…"
        const val STATUS_BREAK = "休息一下"
        const val STATUS_READY = "准备就绪"
        const val STATUS_PAUSED = "已暂停"
        const val COMPLETED_TITLE = "本次专注完成"
        const val COMPLETED_MESSAGE = "做得很好，休息一下吧。识别结果仅供辅助参考，节奏由你自己掌握。"
        const val STATS_TODAY = "今日专注"
        const val STATS_COUNT = "完成次数"
        const val STATS_STREAK = "连续天数"
        const val MINUTES_UNIT = "分钟"
        const val TIMES_UNIT = "次"
        const val DAYS_UNIT = "天"
        const val GOAL_TITLE = "自习目标"
        const val GOAL_FORMAT = "每日目标 %d 分钟"
        const val RECORDS_TITLE = "最近专注记录"
        const val RECORDS_EMPTY = "还没有专注记录，开始第一段专注吧"
        const val PLAN_ENTRY = "生成学习计划"
        const val PLAN_PROMPT = "请根据我今天的课程、任务和考试安排，为我生成一份自习计划。"
        const val FINISHED_TAG = "已完成"
        const val UNFINISHED_TAG = "提前结束"
    }

}
