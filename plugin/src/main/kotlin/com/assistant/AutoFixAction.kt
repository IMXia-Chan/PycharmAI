package com.assistant

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.ui.Messages

/** 选中一段代码 → AI 自动修复,可一键替换选区。 */
class AutoFixAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val editor = FileEditorManager.getInstance(project).selectedTextEditor ?: return
        val code = EditorOps.currentCode(editor)
        if (code.isBlank()) {
            Messages.showWarningDialog(project, "请先选中一段代码。", "自动修复")
            return
        }
        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "AI 正在修复…", false) {
            override fun run(indicator: ProgressIndicator) {
                var result: String? = null
                var error: String? = null
                try {
                    result = BackendClient.fix(code)
                } catch (ex: Exception) {
                    error = "请求失败:${ex.message ?: "请确认后端已启动"}"
                }
                ApplicationManager.getApplication().invokeLater {
                    val r = result
                    if (r != null) {
                        AiResultDialog(project, "自动修复", r) { EditorOps.replace(editor, r) }.show()
                    } else {
                        AiResultDialog(project, "自动修复", error!!).show()
                    }
                }
            }
        })
    }
}
