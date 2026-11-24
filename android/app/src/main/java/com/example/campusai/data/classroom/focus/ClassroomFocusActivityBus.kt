package com.example.campusai.data.classroom.focus

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow

/**
 * 单个原生课堂 ViewModel 的学生主动操作流。
 *
 * ViewModel 只在**真实发生**的学生动作里发布事件；课堂观察控制器只在开启时订阅。
 * 没有订阅者时事件直接丢弃（`extraBufferCapacity` 只用于避免发布方挂起），
 * 因此不会把课间操作带到下一节课。自动翻页/重放由发布方与模型来源枚举双重排除。
 */
class ClassroomFocusActivityBus(private val now: () -> Long) {
    private val _events = MutableSharedFlow<ClassroomFocusEvent>(extraBufferCapacity = 16)
    val events = _events.asSharedFlow()

    fun publish(type: ClassroomFocusEventType) {
        _events.tryEmit(ClassroomFocusEvent(type, now()))
    }
}
