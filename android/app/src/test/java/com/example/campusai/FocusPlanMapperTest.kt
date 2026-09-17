package com.example.campusai

import com.example.campusai.data.model.FocusPlanStep
import com.example.campusai.data.model.FocusPlanStepStatus
import com.example.campusai.data.remote.TaskBreakdownResponseDto
import com.example.campusai.data.remote.TaskBreakdownStepDto
import com.example.campusai.data.repository.toFocusPlan
import org.junit.Assert.assertEquals
import org.junit.Test

class FocusPlanMapperTest {
    @Test
    fun mapsServerStepsIntoAnOrderedPendingPlan() {
        val response = TaskBreakdownResponseDto(
            mode = "rule_fallback",
            goal = "复习数据结构",
            related_task_id = "task-1",
            related_task_title = "复习数据结构",
            steps = listOf(
                TaskBreakdownStepDto(2, "练习", "完成练习", 25, listOf(1), "练习完成"),
                TaskBreakdownStepDto(1, "准备", "打开资料", 10, emptyList(), "资料已打开"),
            ),
        )

        val plan = response.toFocusPlan("task-1", "备用标题")

        assertEquals(listOf(1, 2), plan.steps.map { it.stepNumber })
        assertEquals("复习数据结构", plan.taskTitle)
        assertEquals(FocusPlanStepStatus.PENDING, plan.currentStep?.status)
        assertEquals(listOf(1), plan.steps[1].dependencies)
    }

    @Test
    fun preservesEveryStructuralFieldIncludingKnowledgeEvidence() {
        val response = TaskBreakdownResponseDto(
            mode = "llm",
            goal = "申请助学金",
            related_task_id = "task-9",
            related_task_title = "申请助学金",
            steps = listOf(
                TaskBreakdownStepDto(
                    step_number = 1,
                    title = "准备证明材料",
                    description = "整理家庭情况调查表",
                    estimated_minutes = 30,
                    dependencies = emptyList(),
                    completion_criteria = "材料齐全",
                    is_policy_step = true,
                    knowledge_source = "助学金评定办法",
                    knowledge_document_id = "doc_7",
                    knowledge_status = "cited",
                ),
            ),
        )

        val step = response.toFocusPlan("task-9", "备用标题").steps.single()

        assertEquals(1, step.stepNumber)
        assertEquals("准备证明材料", step.title)
        assertEquals("整理家庭情况调查表", step.description)
        assertEquals(30, step.estimatedMinutes)
        assertEquals("材料齐全", step.completionCriteria)
        assertEquals(true, step.isPolicyStep)
        assertEquals("助学金评定办法", step.knowledgeSource)
        // 新增: 服务端校验用的文档 ID 与人工确认状态不得在移动端丢失
        assertEquals("doc_7", step.knowledgeDocumentId)
        assertEquals("cited", step.knowledgeStatus)
    }

    @Test
    fun prerequisiteHintDescribesRequiredEarlierSteps() {
        val noDeps = TaskBreakdownStepDto(1, "准备", "打开资料", 10, emptyList(), "资料已打开")
        val oneDep = TaskBreakdownStepDto(2, "练习", "完成练习", 25, listOf(1), "练习完成")
        val manyDeps = TaskBreakdownStepDto(3, "总结", "写总结", 15, listOf(2, 1), "总结写完")

        val plan = TaskBreakdownResponseDto(
            mode = "llm",
            goal = "复习数据结构",
            steps = listOf(noDeps, oneDep, manyDeps),
        ).toFocusPlan("task-1", "备用标题")

        assertEquals(null, plan.steps[0].prerequisiteHint)
        assertEquals("需先完成第 1 步", plan.steps[1].prerequisiteHint)
        // 依赖顺序由服务端保证升序,展示时再排一次避免乱序文案
        assertEquals("需先完成第 1、2 步", plan.steps[2].prerequisiteHint)
    }

    @Test
    fun knowledgeHintFallsBackToConfirmationWhenEvidenceIsMissing() {
        val cited = TaskBreakdownStepDto(
            1, "查阅办法", "读文件", 10, emptyList(), "已阅读",
            is_policy_step = true,
            knowledge_source = "助学金评定办法",
            knowledge_status = "cited",
        )
        val unconfirmed = TaskBreakdownStepDto(
            2, "咨询辅导员", "问清楚口径", 15, listOf(1), "已确认",
            is_policy_step = true,
            knowledge_status = "needs_confirmation",
        )
        val ordinary = TaskBreakdownStepDto(3, "整理笔记", "归档", 10, listOf(2), "已归档")

        val plan = TaskBreakdownResponseDto(
            mode = "llm",
            goal = "申请助学金",
            steps = listOf(cited, unconfirmed, ordinary),
        ).toFocusPlan("task-1", "备用标题")

        assertEquals("参考：助学金评定办法", plan.steps[0].knowledgeHint)
        // 没有来源时不能静默留空,必须提示人工确认
        assertEquals("政策相关,暂无权威资料,建议先向辅导员确认", plan.steps[1].knowledgeHint)
        assertEquals(null, plan.steps[2].knowledgeHint)
    }

    @Test
    fun legacyPolicyStepWithoutKnowledgeStatusStillRequestsConfirmation() {
        val legacy = FocusPlanStep(
            stepNumber = 1,
            title = "咨询辅导员",
            description = "确认申请要求",
            estimatedMinutes = 15,
            completionCriteria = "已确认",
            isPolicyStep = true,
        )

        assertEquals("政策相关,暂无权威资料,建议先向辅导员确认", legacy.knowledgeHint)
    }
}
