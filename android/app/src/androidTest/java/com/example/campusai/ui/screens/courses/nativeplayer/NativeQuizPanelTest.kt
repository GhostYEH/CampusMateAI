package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.example.campusai.data.classroom.nativeplayer.NativeAnswer
import com.example.campusai.data.classroom.nativeplayer.NativeQuestion
import com.example.campusai.data.classroom.nativeplayer.NativeQuiz
import com.example.campusai.data.classroom.nativeplayer.NativeQuizOption
import com.example.campusai.data.classroom.nativeplayer.NativeQuizSubmitState
import com.example.campusai.data.classroom.nativeplayer.NativeQuizUiState
import org.junit.Rule
import org.junit.Test

class NativeQuizPanelTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun submissionStaysVisibleOnAShortLargeTextViewport() {
        val questions = (1..6).map { number ->
            NativeQuestion(
                id = "question-$number",
                number = number,
                type = "single",
                question = "请选择正确的答案。",
                options = listOf(NativeQuizOption("A", "A"), NativeQuizOption("B", "B")),
            )
        }
        val state = mutableStateOf(NativeQuizUiState())

        composeRule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(density.density, fontScale = 1.3f)) {
                Box(Modifier.size(width = 320.dp, height = 265.dp)) {
                    NativeClassroomTheme(paper = true) {
                        NativeQuizPanel(
                            quiz = NativeQuiz(questions),
                            sceneTitle = "随堂测验",
                            state = state.value,
                            onAnswer = { _, _ -> },
                            onSubmit = {
                                state.value = state.value.copy(
                                    submitState = NativeQuizSubmitState.Submitting,
                                    saving = true,
                                )
                            },
                            onRetry = {},
                            onSelfCheck = { _, _ -> },
                            onFinishReview = {},
                        )
                    }
                }
            }
        }

        val submit = composeRule.onNodeWithText("提交答案")
        submit.assertIsDisplayed().assertIsNotEnabled()

        composeRule.runOnIdle {
            state.value = state.value.copy(answers = questions.associate { it.id to NativeAnswer(setOf("A")) })
        }
        submit.assertIsDisplayed().assertIsEnabled().performClick()
        composeRule.onNodeWithText("提交确认中…").assertIsDisplayed().assertIsNotEnabled()
    }
}
