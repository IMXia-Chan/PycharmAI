package com.assistant

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages

/** 把当前选中的代码保存到「代码片段库」的通用逻辑(工具窗口与菜单共用)。 */
object SnippetSaver {
    fun saveCurrent(project: Project) {
        val editor = FileEditorManager.getInstance(project).selectedTextEditor
        val code = if (editor != null) EditorOps.currentCode(editor) else ""
        if (code.isBlank()) {
            Messages.showWarningDialog(project, "请先在编辑器里选中要保存的代码。", "保存代码片段")
            return
        }
        val title = Messages.showInputDialog(
            project, "给这个片段起个名字(方便以后找):", "保存代码片段", null
        ) ?: return

        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "保存片段…", false) {
            override fun run(indicator: ProgressIndicator) {
                try {
                    BackendClient.addSnippet(title, code, "")
                } catch (ex: Exception) {
                    ApplicationManager.getApplication().invokeLater {
                        Messages.showErrorDialog(project, ex.message ?: "保存失败", "错误")
                    }
                    return
                }
                ApplicationManager.getApplication().invokeLater {
                    Messages.showInfoMessage(project, "已保存代码片段「${title.ifBlank { "(无标题)" }}」。", "保存代码片段")
                }
            }
        })
    }
}
