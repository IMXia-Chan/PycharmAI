package com.assistant

import com.intellij.ide.BrowserUtil
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
import java.awt.datatransfer.DataFlavor
import java.awt.datatransfer.StringSelection
import java.awt.datatransfer.Transferable
import javax.swing.DefaultListCellRenderer
import javax.swing.DefaultListModel
import javax.swing.JButton
import javax.swing.JComponent
import javax.swing.JLabel
import javax.swing.JList
import javax.swing.JPanel
import javax.swing.JSplitPane
import javax.swing.ListSelectionModel
import javax.swing.TransferHandler

class LibraryToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val content = toolWindow.contentManager.factory.createContent(LibraryPanel(project), "", false)
        toolWindow.contentManager.addContent(content)
    }
}

/** 文件库窗口:左侧本地记录(按文件分组),右侧唯一「候选库」(临时上传区)。 */
private class LibraryPanel(private val myProject: Project) : SimpleToolWindowPanel(true, true) {

    private val recordsModel = DefaultListModel<LocalRecord>()
    private val recordsList = JBList(recordsModel)
    private val candidateModel = DefaultListModel<LocalRecord>()
    private val candidateList = JBList(candidateModel)

    init {
        recordsList.selectionMode = ListSelectionModel.MULTIPLE_INTERVAL_SELECTION
        recordsList.cellRenderer = recordRenderer()
        recordsList.dragEnabled = true
        recordsList.transferHandler = dragSourceHandler()

        candidateList.selectionMode = ListSelectionModel.SINGLE_SELECTION
        candidateList.cellRenderer = recordRenderer()
        candidateList.transferHandler = dropTargetHandler()

        val right = JPanel(BorderLayout())
        right.add(JLabel("候选库（临时上传区）"), BorderLayout.NORTH)
        right.add(JBScrollPane(candidateList), BorderLayout.CENTER)

        val split = JSplitPane(JSplitPane.HORIZONTAL_SPLIT, JBScrollPane(recordsList), right)
        split.resizeWeight = 0.55
        setContent(split)

        val toolbar = JPanel(FlowLayout(FlowLayout.LEFT))
        toolbar.add(JButton("刷新").apply { addActionListener { refresh() } })
        toolbar.add(JButton("删除记录").apply { addActionListener { deleteSelected() } })
        toolbar.add(JButton("加入候选库").apply { addActionListener { addSelected() } })
        toolbar.add(JButton("移除").apply { addActionListener { removeSelected() } })
        toolbar.add(JButton("清空候选库").apply { addActionListener { clearCandidate() } })
        toolbar.add(JButton("上传网页").apply { addActionListener { uploadWeb() } })
        toolbar.add(JButton("打开网页").apply { addActionListener { openWeb(false) } })
        setToolbar(toolbar)

        refresh()
    }

    private fun recordRenderer(): DefaultListCellRenderer =
        object : DefaultListCellRenderer() {
            override fun getListCellRendererComponent(
                list: JList<*>, value: Any?, index: Int, isSelected: Boolean, cellHasFocus: Boolean,
            ): JComponent {
                val label = super.getListCellRendererComponent(list, value, index, isSelected, cellHasFocus) as JLabel
                label.text = formatRecord(value as LocalRecord)
                return label
            }
        }

    private fun formatRecord(r: LocalRecord): String {
        if (r.kind == "snippet") {
            val t = r.title.ifBlank { "(无标题)" }
            val short = if (t.length > 30) t.take(30) + "…" else t
            return "📌 [片段] $short"
        }
        val kind = when (r.kind) {
            "explain" -> "代码解释"
            "error-explain" -> "报错解释"
            else -> "报错记录"
        }
        val t = r.title.ifBlank { r.message.ifBlank { "(无标题)" } }
        val short = if (t.length > 24) t.take(24) + "…" else t
        return "📄 ${r.filename} ｜ [$kind] $short"
    }

    private fun dragSourceHandler(): TransferHandler =
        object : TransferHandler() {
            override fun getSourceActions(c: JComponent): Int = TransferHandler.COPY
            override fun createTransferable(c: JComponent): Transferable? {
                val list = c as? JList<*> ?: return null
                val ids = list.selectedValuesList.filterIsInstance<LocalRecord>().map { it.id }
                if (ids.isEmpty()) return null
                return StringSelection(ids.joinToString("\n"))
            }
        }

    private fun dropTargetHandler(): TransferHandler =
        object : TransferHandler() {
            override fun canImport(support: TransferSupport): Boolean =
                support.isDataFlavorSupported(DataFlavor.stringFlavor)

            override fun importData(support: TransferSupport): Boolean {
                if (!canImport(support)) return false
                val data = support.transferable.getTransferData(DataFlavor.stringFlavor) as? String ?: return false
                val ids = data.split("\n").filter { it.isNotBlank() }
                if (ids.isEmpty()) return false
                LocalLibraryStore.addToCandidate(ids)
                refresh()
                return true
            }
        }

    private fun refresh() {
        recordsModel.clear()
        LocalLibraryStore.records().sortedBy { it.filename }.forEach { recordsModel.addElement(it) }
        candidateModel.clear()
        LocalLibraryStore.candidateRecords().forEach { candidateModel.addElement(it) }
    }

    private fun selectedRecords(): List<LocalRecord> = recordsList.selectedValuesList

    private fun deleteSelected() {
        val sel = selectedRecords()
        if (sel.isEmpty()) return
        val ok = Messages.showYesNoDialog(
            myProject, "确定删除选中的 ${sel.size} 条记录吗?", "删除记录", Messages.getQuestionIcon()
        )
        if (ok != Messages.YES) return
        sel.forEach { LocalLibraryStore.deleteRecord(it.id) }
        refresh()
    }

    private fun addSelected() {
        val ids = selectedRecords().map { it.id }
        if (ids.isEmpty()) {
            Messages.showInfoMessage(myProject, "请先在左侧选中要加入候选库的记录。", "加入候选库")
            return
        }
        LocalLibraryStore.addToCandidate(ids)
        refresh()
    }

    private fun removeSelected() {
        val sel = candidateList.selectedValuesList
        if (sel.isEmpty()) return
        sel.forEach { LocalLibraryStore.removeFromCandidate(it.id) }
        refresh()
    }

    private fun clearCandidate() {
        LocalLibraryStore.clearCandidate()
        refresh()
    }

    private fun uploadWeb() {
        val candidates = LocalLibraryStore.candidateRecords()
        if (candidates.isEmpty()) {
            Messages.showInfoMessage(myProject, "候选库还是空的。先把要上传的记录拖进来或「加入候选库」。", "上传网页")
            return
        }
        ProgressManager.getInstance().run(object : Task.Backgroundable(myProject, "上传记录…", false) {
            override fun run(indicator: ProgressIndicator) {
                val snippets = candidates.filter { it.kind == "snippet" }
                val records = candidates.filter { it.kind != "snippet" }
                try {
                    snippets.forEach { BackendClient.addSnippet(it.title, it.code, it.message) }
                    if (records.isNotEmpty()) {
                        BackendClient.uploadRecords(
                            records.map {
                                Record(it.category, it.title, it.message, it.filename, it.line, it.code, it.severity)
                            }
                        )
                    }
                } catch (ex: Exception) {
                    ApplicationManager.getApplication().invokeLater {
                        Messages.showErrorDialog(myProject, ex.message ?: "上传失败,请确认后端已启动", "错误")
                    }
                    return
                }
                LocalLibraryStore.clearCandidate()
                ApplicationManager.getApplication().invokeLater {
                    refresh()
                    openWeb(true)
                }
            }
        })
    }

    private fun openWeb(withNotes: Boolean) {
        if (!BackendClient.healthOk()) {
            Messages.showWarningDialog(
                myProject, "后端未启动,网页打不开。\n请先在项目目录运行:python -m backend.main", "网页"
            )
            return
        }
        val token = BackendClient.openWeb()
        if (token.isBlank()) {
            Messages.showWarningDialog(myProject, "网页入口令牌获取失败,请稍后重试。", "网页")
            return
        }
        val base = AssistantSettings.getInstance().state.backendUrl.trimEnd('/')
        val url = base + "/web?token=" + token + if (withNotes) "#notes" else ""
        BrowserUtil.open(url)
    }
}
