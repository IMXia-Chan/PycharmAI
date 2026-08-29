package com.assistant

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.ui.SimpleToolWindowPanel
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.components.JBList
import com.intellij.ui.components.JBScrollPane
import java.awt.BorderLayout
import java.awt.FlowLayout
import java.awt.Toolkit
import java.awt.datatransfer.StringSelection
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.JPanel
import javax.swing.JSplitPane
import javax.swing.JTextArea

/** 「代码片段」工具窗口:左边是片段列表,右边是代码详情;可保存/复制/删除。 */
class SnippetToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val content = toolWindow.contentManager.factory.createContent(SnippetPanel(project), "", false)
        toolWindow.contentManager.addContent(content)
    }
}

private class SnippetPanel(private val myProject: Project) : SimpleToolWindowPanel(true, true) {

    private val listModel = DefaultListModel<String>()
    private val list = JBList(listModel)
    private val codeArea = JTextArea().apply {
        isEditable = false
        lineWrap = false
    }
    private var lastSnippets: List<Snippet> = emptyList()

    init {
        val split = JSplitPane(JSplitPane.HORIZONTAL_SPLIT, JBScrollPane(list), JBScrollPane(codeArea))
        split.resizeWeight = 0.3
        setContent(split)

        val toolbar = JPanel(FlowLayout(FlowLayout.LEFT))
        val refreshBtn = JButton("刷新")
        val saveBtn = JButton("保存当前代码")
        val copyBtn = JButton("复制")
        val deleteBtn = JButton("删除")
        toolbar.add(refreshBtn)
        toolbar.add(saveBtn)
        toolbar.add(copyBtn)
        toolbar.add(deleteBtn)
        setToolbar(toolbar)

        refreshBtn.addActionListener { refresh() }
        saveBtn.addActionListener { SnippetSaver.saveCurrent(myProject); refresh() }
        copyBtn.addActionListener { copySelected() }
        deleteBtn.addActionListener { deleteSelected() }
        list.addListSelectionListener { showSelected() }

        refresh()
    }

    private fun refresh() {
        ProgressManager.getInstance().run(object : Task.Backgroundable(myProject, "加载片段…", false) {
            override fun run(indicator: ProgressIndicator) {
                val snippets = try {
                    BackendClient.snippets()
                } catch (_: Exception) {
                    emptyList()
                }
                lastSnippets = snippets
                ApplicationManager.getApplication().invokeLater {
                    listModel.clear()
                    snippets.forEach {
                        listModel.addElement(it.title.ifBlank { it.code.lineSequence().firstOrNull() ?: "(无标题)" })
                    }
                    if (snippets.isEmpty()) {
                        codeArea.text = "还没有保存任何代码片段。\n\n点「保存当前代码」把选中的代码存进来。"
                    }
                }
            }
        })
    }

    private fun showSelected() {
        val s = lastSnippets.getOrNull(list.selectedIndex) ?: return
        codeArea.text = buildString {
            if (s.title.isNotBlank()) append(s.title).append("\n\n")
            append(s.code)
            if (s.note.isNotBlank()) append("\n\n// 备注:").append(s.note)
        }
        codeArea.caretPosition = 0
    }

    private fun copySelected() {
        val s = lastSnippets.getOrNull(list.selectedIndex) ?: return
        Toolkit.getDefaultToolkit().systemClipboard.setContents(StringSelection(s.code), null)
    }

    private fun deleteSelected() {
        val s = lastSnippets.getOrNull(list.selectedIndex) ?: return
        val ok = Messages.showYesNoDialog(
            myProject, "确定删除片段「${s.title.ifBlank { "(无标题)" }}」吗?", "删除片段", Messages.getQuestionIcon()
        )
        if (ok != Messages.YES) return
        ProgressManager.getInstance().run(object : Task.Backgroundable(myProject, "删除片段…", false) {
            override fun run(indicator: ProgressIndicator) {
                try {
                    BackendClient.deleteSnippet(s.id)
                } catch (ex: Exception) {
                    ApplicationManager.getApplication().invokeLater {
                        Messages.showErrorDialog(myProject, ex.message ?: "删除失败", "错误")
                    }
                    return
                }
                ApplicationManager.getApplication().invokeLater { refresh() }
            }
        })
    }
}
