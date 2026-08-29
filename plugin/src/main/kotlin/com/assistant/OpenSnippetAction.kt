package com.assistant

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.wm.ToolWindowManager

/** 打开/激活「代码片段」工具窗口(快捷键 Ctrl+Alt+W)。 */
class OpenSnippetAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        ToolWindowManager.getInstance(project).getToolWindow("代码片段")?.activate(null)
    }
}
