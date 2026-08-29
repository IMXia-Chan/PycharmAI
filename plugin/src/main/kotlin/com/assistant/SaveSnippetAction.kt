package com.assistant

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent

/** 菜单/右键入口:把选中的代码保存到代码片段库。 */
class SaveSnippetAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        SnippetSaver.saveCurrent(project)
    }
}
