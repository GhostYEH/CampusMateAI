import { useState } from 'react';

import { cn } from '../utils/cn.js';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card.jsx';
import { Button } from '../ui/button.jsx';

/**
 * 移植自参考项目 `components/scene-renderers/quiz-renderer.tsx`。
 *
 * 机械改写：擦除类型、去掉 `'use client'`、`@/components/ui/*` 与 `@/lib/utils`
 * 改为相对路径。类名逐字保留。
 */
export function QuizRenderer({ content, mode, sceneId: _sceneId }) {
  const [answers, setAnswers] = useState({});

  const handleAnswerChange = (questionId, answer) => {
    setAnswers((prev) => ({ ...prev, [questionId]: answer }));
  };

  return (
    <div className="w-full h-full overflow-y-auto p-8">
      <div className="max-w-3xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">Quiz</h1>
        {content.questions.map((question) => (
          <Card key={question.id}>
            <CardHeader>
              <CardTitle>{question.question}</CardTitle>
            </CardHeader>
            <CardContent>
              {question.type === 'single' && question.options && (
                <div className="space-y-2">
                  {question.options.map((option, optIndex) => {
                    // Normalize: options may be QuizOption objects or plain strings from AI
                    const optionValue = typeof option === 'string' ? option : option.value;
                    const optionLabel = typeof option === 'string' ? option : option.label;
                    const letterPrefix = String.fromCharCode(65 + optIndex); // A, B, C, D...

                    return (
                      <label
                        key={`${question.id}-opt-${optIndex}`}
                        className={cn(
                          'flex items-center space-x-2 p-2 rounded cursor-pointer hover:bg-muted',
                          answers[question.id] === (optionValue || letterPrefix) && 'bg-muted',
                        )}
                      >
                        <input
                          type="radio"
                          name={question.id}
                          value={optionValue || letterPrefix}
                          checked={answers[question.id] === (optionValue || letterPrefix)}
                          onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                          className="size-4"
                        />
                        <span>
                          {letterPrefix}. {optionLabel}
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
              {question.type === 'short_answer' && (
                <textarea
                  className="w-full min-h-24 p-2 border rounded"
                  placeholder="Enter your answer..."
                  value={answers[question.id] || ''}
                  onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                />
              )}
            </CardContent>
          </Card>
        ))}
        {mode === 'autonomous' && (
          <div className="flex justify-end">
            <Button>Submit Answers</Button>
          </div>
        )}
      </div>
    </div>
  );
}
