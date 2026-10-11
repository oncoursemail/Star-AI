"""STAR's native Windows desktop shell (PySide6).

This is a real local-model client, not a static UI mockup. Heavy work always uses
worker threads; Windows .exe is produced by GitHub Actions on a Windows runner.
"""
from __future__ import annotations
from dataclasses import asdict, replace
import html
import json
from pathlib import Path
import subprocess
import sys
import uuid

from PySide6.QtCore import Qt, QThread, Signal, QSize, QUrl, QTimer, QPropertyAnimation, QEasingCurve, QEvent
from PySide6.QtGui import QFont, QIcon, QDesktopServices, QPixmap, QPainter, QLinearGradient, QColor, QPen
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QScrollArea, QFileDialog,
    QComboBox, QCheckBox, QMessageBox, QInputDialog, QStackedWidget, QFormLayout, QSpinBox,
    QSplitter, QListWidget, QListWidgetItem, QSizePolicy, QProgressBar, QGraphicsOpacityEffect)

from .desktop_core import Settings, app_data, Conversations, query_models, run_task, check_studio
from .providers import uses_star_server
from .media_features import video_frames, transcribe_audio, local_speak
from .memory import Memory
from .local_runtime import Runtime
from .version import __version__
from .visuals import qt_icon
from .design_system import COLORS, MOTION_MS, stylesheet
from .analytics import get_dashboard
from .analytics_ui import ActivityChart, MetricCard

STYLE = stylesheet()



def label(text, kind=None, selectable=False):
    w = QLabel(text)
    if kind:
        w.setObjectName(kind)
    w.setWordWrap(True)
    if selectable:
        w.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return w


def button(text, primary=False, callback=None, subtle=False):
    w = QPushButton(text)
    if primary:
        w.setObjectName('Primary')
    if subtle:
        w.setObjectName('Subtle')
    w.setCursor(Qt.PointingHandCursor)
    if callback:
        w.clicked.connect(callback)
    return w


def row(*widgets, spacing=8):
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(0, 0, 0, 0)
    for w in widgets:
        if isinstance(w, (QHBoxLayout, QVBoxLayout)):
            layout.addLayout(w)
        else:
            layout.addWidget(w)
    return layout


class Job(QThread):
    success = Signal(object)
    failure = Signal(str)
    event = Signal(object)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs

    def run(self):
        try:
            self.success.emit(self.fn(*self.args, **self.kwargs))
        except Exception as error:
            self.failure.emit(f'{type(error).__name__}: {error}')


class ChatBubble(QFrame):
    """Quiet, copyable conversation row. User messages remain visually distinct."""
    def __init__(self, who, text):
        super().__init__()
        self.setObjectName('UserBubble' if who == 'user' else 'EventBubble' if who == 'event' else 'StarBubble')
        self.setMaximumWidth(790)
        self.setAccessibleName(('You' if who == 'user' else 'STAR' if who == 'assistant' else 'Activity') + ' message')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(17, 14, 17, 15)
        outer.setSpacing(8)
        header = QWidget()
        top = QHBoxLayout(header)
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        icon = QLabel()
        icon.setFixedSize(22, 22)
        if who == 'assistant':
            icon.setPixmap(qt_icon('star', COLORS['gold'], 20).pixmap(20,20))
        else:
            icon.setPixmap(qt_icon('chat',COLORS['muted'],17).pixmap(17,17))
        top.addWidget(icon)
        role = label('STAR' if who == 'assistant' else 'You' if who == 'user' else 'Activity','Section')
        top.addWidget(role)
        top.addStretch(1)
        copy = button('Copy',subtle=True,callback=lambda:QApplication.clipboard().setText(text))
        copy.setIcon(qt_icon('copy', COLORS['muted'], 15))
        copy.setToolTip('Copy this message')
        copy.setAccessibleName('Copy message to clipboard')
        top.addWidget(copy)
        outer.addWidget(header)
        body = label(text, selectable=True)
        body.setTextFormat(Qt.PlainText)
        body.setWordWrap(True)
        body.setStyleSheet('font-size: 14px; color: #E5E8ED; line-height: 1.45;')
        outer.addWidget(body)




class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'STAR Intelligence · v{__version__}')
        self.setMinimumSize(1050, 680)
        self.resize(1440, 860)
        self.settings_file = app_data() / 'settings.json'
        self.cfg = Settings.load(self.settings_file)
        self.chats = Conversations(app_data() / 'conversations.sqlite3')
        self.attachments: list[Path] = []
        self.jobs: set[Job] = set()
        self.busy = False
        self.last_answer = ''
        self.runtime = Runtime()
        self.animations = []
        self.thinking_frame = 0
        self.thinking_timer = QTimer(self)
        self.thinking_timer.timeout.connect(self.animate_thinking)
        root = QWidget()
        root.setObjectName('Root')
        self.setCentralWidget(root)
        horizontal = QHBoxLayout(root)
        horizontal.setContentsMargins(0,0,0,0)
        horizontal.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName('Sidebar')
        self.sidebar.setFixedWidth(231)
        horizontal.addWidget(self.sidebar)
        left = QVBoxLayout(self.sidebar)
        left.setContentsMargins(14, 21, 14, 18)
        left.setSpacing(9)
        brand_row = QWidget()
        br = QHBoxLayout(brand_row)
        br.setContentsMargins(8, 0, 0, 0)
        br.setSpacing(10)
        star_icon = QLabel()
        star_icon.setPixmap(qt_icon('star',COLORS['gold'],34).pixmap(34,34))
        br.addWidget(star_icon)
        br.addWidget(label('STAR','Brand'))
        br.addStretch(1)
        left.addWidget(brand_row)
        left.addWidget(label('INTELLIGENCE WORKSPACE', 'Small'))
        left.addSpacing(23)
        left.addWidget(label('WORKSPACE', 'Small'))
        self.navs = []
        self.nav_destinations = []
        # Chat and real Analytics are the primary destinations; advanced
        # configuration is visually secondary, not a wall of equal-weight tabs.
        sections=[('Chat','chat',0),('Analytics','analytics',6),('Projects','projects',1),
                  ('Roblox Studio','tools',2),('Image Lab','image',3),
                  ('STAR Brain','brain',5),('Settings','settings',4)]
        for title, icon_name, dest in sections:
            nav=button(title)
            nav.setObjectName('Nav')
            nav.setCheckable(True)
            nav.setIcon(qt_icon(icon_name,COLORS['muted'],19))
            nav.setIconSize(QSize(19,19))
            nav.setMinimumHeight(41)
            nav.clicked.connect(lambda checked=False, n=dest:self.show_page(n))
            self.navs.append(nav)
            self.nav_destinations.append(dest)
            left.addWidget(nav)
        left.addStretch(1)
        left.addWidget(label('CURRENT PROJECT', 'Small'))
        self.project_edit=QLineEdit(self.cfg.project)
        self.project_edit.setToolTip('All history and analytics stay scoped to this project')
        self.project_edit.editingFinished.connect(self.change_project)
        left.addWidget(self.project_edit)
        left.addSpacing(9)
        self.side_brain = button('Set up STAR Brain',primary=True,callback=lambda:self.show_page(5))
        self.side_brain.setIcon(qt_icon('download',COLORS['gold_ink'],17))
        left.addWidget(self.side_brain)
        left.addSpacing(11)
        left.addWidget(label('LOCAL · PRIVATE BY DEFAULT', 'Small'))
        left.addWidget(label(f'GENESIS  v{__version__}', 'Version'))

        self.pages = QStackedWidget()
        horizontal.addWidget(self.pages,stretch=1)
        self.chat_page = self.create_chat_page()
        self.project_page = self.create_projects_page()
        self.tools_page = self.create_tools_page()
        self.image_page = self.create_image_page()
        self.settings_page = self.create_settings_page()
        self.brain_page = self.create_brain_page()
        self.analytics_page = self.create_analytics_page()
        for pg in (self.chat_page,self.project_page,self.tools_page,self.image_page,
                   self.settings_page,self.brain_page,self.analytics_page):
            self.pages.addWidget(pg)
        self.dashboard_timer = QTimer(self)
        self.dashboard_timer.timeout.connect(self.refresh_analytics)
        self.dashboard_timer.start(5500)
        self.show_page(0)
        self.load_chat()
        self.refresh_project_info()
        from .brain_setup import BrainInstall
        if BrainInstall.load(app_data()/'brain.json'):
            QTimer.singleShot(350,self.resume_brain)
        else:
            self.show_page(5)


    def eventFilter(self, watched, event):
        # Keyboard-first composing: Ctrl+Enter sends, Enter adds a new line.
        if (hasattr(self, 'prompt') and watched is self.prompt
                and event.type() == QEvent.KeyPress
                and event.key() in (Qt.Key_Return, Qt.Key_Enter)
                and event.modifiers() & Qt.ControlModifier):
            self.send_message()
            return True
        return super().eventFilter(watched, event)

    def show_page(self, index):
        self.pages.setCurrentIndex(index)
        for i, nav in enumerate(self.navs):
            nav.setChecked(self.nav_destinations[i] == index)
        if index == 6:
            self.refresh_analytics()
        if index == 1:
            self.refresh_project_info()
        if index == 2:
            self.refresh_tool_info()

    def create_header(self, title, subtitle):
        header=QFrame(); header.setObjectName('TopBar')
        outer=QHBoxLayout(header); outer.setContentsMargins(29,20,29,17)
        left=QVBoxLayout();left.setSpacing(4)
        left.addWidget(label(title,'Header'));left.addWidget(label(subtitle,'Muted'))
        outer.addLayout(left);outer.addStretch(1)
        outer.addWidget(label(f'GENESIS  v{__version__}','Version'))
        return header

    def create_hero(self):
        hero=QFrame();hero.setObjectName('Hero')
        lay=QVBoxLayout(hero)
        lay.setContentsMargins(25,23,25,22)
        lay.setSpacing(10)
        lay.addWidget(label('✦  CREATE WITH STAR','Kicker'))
        lay.addWidget(label('What are we building today?','HeroTitle'))
        lay.addWidget(label('Ask a question, share a design reference, or build something in Roblox.','Muted'))
        options = QWidget()
        buttons = QHBoxLayout(options)
        buttons.setContentsMargins(0, 9, 0, 0)
        buttons.setSpacing(8)
        for icon_name, title, prompt in [
            ('tools', 'Roblox UI', 'Design and test a native Roblox inventory screen with responsive layout.'),
            ('brain', 'Research', 'Research a robust Roblox client/server architecture for my current project.'),
            ('image', 'Read reference', 'Analyze my attached reference and separate measured details from assumptions.')
        ]:
            action=button(title,callback=lambda checked=False,p=prompt:self.prompt.setPlainText(p))
            action.setIcon(qt_icon(icon_name, COLORS['muted'],16))
            action.setToolTip('Start a '+title.lower()+' request')
            buttons.addWidget(action)
        buttons.addStretch(1)
        lay.addWidget(options)
        return hero

    def create_chat_page(self):
        page=QWidget();page.setObjectName('Content')
        body=QVBoxLayout(page)
        body.setContentsMargins(0,0,0,0);body.setSpacing(0)
        body.addWidget(self.create_header('Chat with STAR', 'Your local intelligence, projects and tools'))
        center=QWidget()
        main=QVBoxLayout(center)
        main.setContentsMargins(30,23,30,19)
        main.setSpacing(14)
        self.hero=self.create_hero()
        main.addWidget(self.hero)
        self.scroll=QScrollArea()
        self.scroll.setWidgetResizable(True)
        content=QWidget()
        self.bubbles=QVBoxLayout(content)
        self.bubbles.setContentsMargins(0,8,4,9)
        self.bubbles.setAlignment(Qt.AlignTop)
        self.bubbles.setSpacing(12)
        self.scroll.setWidget(content)
        main.addWidget(self.scroll,stretch=1)
        self.file_label=label('Drop in your references using Attach · PNG, JPG, video, audio','Small')
        main.addWidget(self.file_label)
        controls=QFrame();controls.setObjectName('EditorBox')
        composer=QVBoxLayout(controls)
        composer.setContentsMargins(14,11,14,12)
        composer.setSpacing(9)
        self.prompt=QTextEdit()
        self.prompt.setPlaceholderText('Message STAR…  describe what you want in your own words')
        self.prompt.setFixedHeight(90)
        self.prompt.setFrameStyle(QFrame.NoFrame)
        self.prompt.setAccessibleName('Message STAR')
        self.prompt.installEventFilter(self)
        composer.addWidget(self.prompt)
        actions=QHBoxLayout()
        actions.setContentsMargins(0,0,0,0)
        actions.setSpacing(8)
        attach=button('Attach',subtle=True,callback=self.attach)
        attach.setIcon(qt_icon('paperclip',COLORS['muted'],17))
        attach.setToolTip('Attach an image, audio or video reference')
        actions.addWidget(attach)
        mic=button('Voice',subtle=True,callback=self.transcribe_attachment)
        mic.setIcon(qt_icon('mic',COLORS['muted'],17))
        actions.addWidget(mic)
        speak=button('Read aloud',subtle=True,callback=self.speak_reply)
        speak.setIcon(qt_icon('sound',COLORS['muted'],17))
        actions.addWidget(speak)
        actions.addStretch(1)
        self.send=button('Send',primary=True,callback=self.send_message)
        self.send.setIcon(qt_icon('arrow',COLORS['gold_ink'],17))
        self.send.setToolTip('Send your request to the local STAR Brain')
        actions.addWidget(self.send)
        composer.addLayout(actions)
        main.addWidget(controls)
        body.addWidget(center,stretch=1)
        self.status=label('Ready · Install STAR Brain to get started','Status')
        self.status.setContentsMargins(30,6,30,13)
        body.addWidget(self.status)
        return page

    def create_projects_page(self):
        page=QWidget(); body=QVBoxLayout(page)
        body.setContentsMargins(0,0,0,0); body.setSpacing(0)
        body.addWidget(self.create_header('Project knowledge','Persistent local conversation history and compaction checkpoints'))
        wrap=QWidget(); lay=QVBoxLayout(wrap); lay.setContentsMargins(26,24,26,26); lay.setSpacing(14)
        lay.addWidget(label('SAVED PROJECTS','Section'))
        self.projects_list=QListWidget()
        self.projects_list.setMaximumHeight(170)
        self.projects_list.itemDoubleClicked.connect(self.select_project)
        lay.addWidget(self.projects_list)
        lay.addWidget(label('COMPACTED TASK CHECKPOINT','Section'))
        self.memory_box=QTextEdit()
        self.memory_box.setReadOnly(True); self.memory_box.setPlaceholderText('No compaction checkpoint yet.')
        lay.addWidget(self.memory_box)
        lay.addWidget(label('Exact task transcripts remain in the local runs folder. Summaries can omit details; refer to original files for precision.','Muted'))
        lay.addWidget(button('Open STAR data folder',callback=self.open_data_folder))
        body.addWidget(wrap,stretch=1)
        return page

    def create_analytics_page(self):
        page=QWidget();page.setObjectName('Content')
        outer=QVBoxLayout(page)
        outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        outer.addWidget(self.create_header('Analytics','Your actual local STAR activity · no tracking or cloud dashboard'))
        scroll=QScrollArea();scroll.setWidgetResizable(True)
        content=QWidget();body=QVBoxLayout(content)
        body.setContentsMargins(29,23,29,30);body.setSpacing(18)
        body.addWidget(label('LAST 14 DAYS  /  PROJECT-SCOPED','Kicker'))
        self.metric_cards={}
        metric_row=QHBoxLayout();metric_row.setSpacing(12)
        for key,title in [('messages','Your messages'),('started','AI runs'),('succeeded','Completed'),('failed','Failed')]:
            card=MetricCard(title)
            self.metric_cards[key]=card
            metric_row.addWidget(card,1)
        body.addLayout(metric_row)
        chart_card=QFrame();chart_card.setObjectName('PanelCard')
        chart_layout=QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(22,19,22,16);chart_layout.setSpacing(10)
        chart_layout.addWidget(label('Task activity','Section'))
        chart_layout.addWidget(label('Actual local task starts per day; zero means no recorded runs.','Muted'))
        self.activity_chart=ActivityChart()
        chart_layout.addWidget(self.activity_chart)
        body.addWidget(chart_card)
        stats=QHBoxLayout();stats.setSpacing(12)
        self.tool_card=MetricCard('Tools used')
        self.latency_card=MetricCard('Median completed task')
        self.policy_card=MetricCard('Blocked tool actions')
        for card in (self.tool_card,self.latency_card,self.policy_card):stats.addWidget(card,1)
        body.addLayout(stats)
        activity=QFrame();activity.setObjectName('PanelCard')
        activity_layout=QVBoxLayout(activity)
        activity_layout.setContentsMargins(22,19,22,19);activity_layout.setSpacing(10)
        activity_layout.addWidget(label('Recent events','Section'))
        self.recent_events=QListWidget()
        self.recent_events.setMinimumHeight(190)
        self.recent_events.setAccessibleName('Actual STAR recent task events')
        activity_layout.addWidget(self.recent_events)
        body.addWidget(activity)
        bottom=QHBoxLayout()
        bottom.addWidget(label('All analytics stay on this computer. No data is uploaded.','Muted'))
        bottom.addStretch(1)
        refresh=button('Refresh',callback=self.refresh_analytics)
        refresh.setIcon(qt_icon('refresh', COLORS['muted'], 16))
        bottom.addWidget(refresh)
        body.addLayout(bottom)
        body.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll,stretch=1)
        return page

    def refresh_analytics(self):
        if not hasattr(self, 'metric_cards') or self.pages.currentIndex() != 6:
            return
        try:
            data=get_dashboard(app_data(),self.cfg.project,days=14)
            for key,card in self.metric_cards.items():card.set_value(data[key])
            self.tool_card.set_value(data['tools'])
            self.latency_card.set_value('—' if data['median_ms'] is None else f"{data['median_ms']/1000:.1f}s")
            self.policy_card.set_value(data['rejected'])
            self.activity_chart.set_trend(data['trend'])
            self.recent_events.clear()
            names={'run_started':'Task started','run_succeeded':'Task completed',
                   'run_failed':'Task failed','tool_completed':'Tool used','tool_rejected':'Tool blocked'}
            for entry in data['recent']:
                timepart=entry['at'].replace('T',' ')[:16]
                self.recent_events.addItem(f"{timepart}  ·  {names.get(entry['type'],entry['type'])}")
            if not data['recent']:
                self.recent_events.addItem('No activity yet. Your first real STAR task will appear here.')
        except Exception as error:
            self.recent_events.clear()
            self.recent_events.addItem('Analytics temporarily unavailable: ' + type(error).__name__)

    def create_tools_page(self):
        page=QWidget(); body=QVBoxLayout(page)
        body.setContentsMargins(0,0,0,0); body.setSpacing(0)
        body.addWidget(self.create_header('Developer workspace','Roblox MCP and restricted local file tools'))
        wrap=QWidget(); lay=QVBoxLayout(wrap);lay.setContentsMargins(26,24,26,26);lay.setSpacing(16)
        panel=QFrame();panel.setObjectName('PanelCard');p=QVBoxLayout(panel);p.setContentsMargins(18,17,18,17)
        p.addWidget(label('Roblox Studio MCP','Section'))
        p.addWidget(label('Enable the server in Roblox Studio → Assistant → Manage MCP Servers. Select an instance ID before editing.','Muted'))
        self.studio_status=label('Studio not checked','Status');p.addWidget(self.studio_status)
        p.addWidget(button('Discover Studio instances',callback=self.discover_studios))
        lay.addWidget(panel)
        panel2=QFrame();panel2.setObjectName('PanelCard');p2=QVBoxLayout(panel2);p2.setContentsMargins(18,17,18,17)
        p2.addWidget(label('Local filesystem tools','Section'))
        p2.addWidget(label('STAR can list, read, search, and (when enabled) write text files under the workspace directory selected in Settings. It cannot access arbitrary PC paths or run an unrestricted shell.','Muted'))
        self.workspace_status=label('', 'Status');p2.addWidget(self.workspace_status)
        lay.addWidget(panel2)
        lay.addWidget(label('GitHub automation uses the separately configured STAR GitHub App and GitHub branch workflow. STAR Desktop does not automatically publish projects or overwrite main.','Muted'))
        lay.addStretch(1);body.addWidget(wrap,stretch=1)
        return page

    def create_image_page(self):
        page=QWidget(); body=QVBoxLayout(page);body.setContentsMargins(0,0,0,0);body.setSpacing(0)
        body.addWidget(self.create_header('STAR Image Lab','Local ComfyUI generation · Workflow-driven · 8 GB GPU-aware'))
        area=QScrollArea();area.setWidgetResizable(True)
        wrap=QWidget();lay=QVBoxLayout(wrap);lay.setContentsMargins(26,24,26,24);lay.setSpacing(14)
        lay.addWidget(label('Generate images using a local ComfyUI API workflow. The workflow must use reviewed local core nodes and an available checkpoint; STAR does not automatically download image weights.','Muted'))
        card=QFrame();card.setObjectName('PanelCard');form=QFormLayout(card)
        form.setContentsMargins(20,20,20,20);form.setSpacing(13)
        self.comfy_workflow=QLineEdit();self.comfy_workflow.setPlaceholderText('C:\\workflows\\image_api.json')
        choose=button('Browse…',callback=self.pick_workflow)
        together=QWidget();together.setLayout(row(self.comfy_workflow,choose))
        form.addRow('API workflow file',together)
        self.comfy_node=QLineEdit('6')
        form.addRow('Text prompt node ID',self.comfy_node)
        self.comfy_port=QSpinBox();self.comfy_port.setRange(1,65535);self.comfy_port.setValue(8188)
        form.addRow('Local ComfyUI port',self.comfy_port)
        self.comfy_prompt=QTextEdit();self.comfy_prompt.setFixedHeight(95)
        self.comfy_prompt.setPlaceholderText('Describe the image you want STAR to generate…')
        form.addRow('Image prompt',self.comfy_prompt)
        self.generate_btn=button('Generate Image →',primary=True,callback=self.generate_image)
        form.addRow('',self.generate_btn)
        lay.addWidget(card)
        self.image_status=label('Image generation has not started','Status');lay.addWidget(self.image_status)
        self.image_preview=QLabel('Generated image preview will appear here')
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setMinimumHeight(220)
        self.image_preview.setStyleSheet('border:1px dashed #3c4a5e; background:#151d27; border-radius:12px; color:#aab7c9;')
        lay.addWidget(self.image_preview)
        lay.addWidget(button('Open generated-image folder',callback=lambda:self.open_specific_folder(app_data()/'generated')))
        lay.addStretch(1)
        area.setWidget(wrap);body.addWidget(area,stretch=1)
        return page

    def create_brain_page(self):
        page=QWidget();page.setObjectName('Content')
        body=QVBoxLayout(page);body.setContentsMargins(0,0,0,0);body.setSpacing(0)
        body.addWidget(self.create_header('STAR Brain','One click to your own private, local AI. No LM Studio. No API keys.'))
        area=QScrollArea();area.setWidgetResizable(True)
        content=QWidget();lay=QVBoxLayout(content);lay.setContentsMargins(32,26,32,28);lay.setSpacing(18)
        hero=QFrame();hero.setObjectName('Hero');box=QVBoxLayout(hero)
        box.setContentsMargins(26,23,26,24);box.setSpacing(11)
        box.addWidget(label('✦  POWERED BY YOUR OWN COMPUTER','Section'))
        box.addWidget(label('Meet STAR Brain.','HeroTitle'))
        box.addWidget(label('One click downloads your private AI, checks every file, and starts STAR on your computer. No account or API key needed.','Muted'))
        self.install_brain_button=button('Download & Launch STAR Brain',primary=True,callback=self.install_star_brain)
        self.install_brain_button.setIcon(qt_icon('download','#242116',20))
        box.addWidget(self.install_brain_button)
        box.addWidget(label('One-time download: about 3.5 GB (Qwen3.5 4B + vision). Keep around 4.5 GB free. After setup, chat runs locally, even without internet.','Small'))
        lay.addWidget(hero)
        card=QFrame();card.setObjectName('PanelCard');cl=QVBoxLayout(card)
        cl.setContentsMargins(22,20,22,22);cl.setSpacing(12)
        cl.addWidget(label('YOUR LOCAL AI · INSTALL STATUS','Section'))
        self.brain_status=label('Not installed yet. Click the button above to begin.','Status')
        cl.addWidget(self.brain_status)
        self.brain_progress=QProgressBar();self.brain_progress.setRange(0,100);self.brain_progress.setValue(0);self.brain_progress.setFormat('%p% downloaded')
        cl.addWidget(self.brain_progress)
        cl.addWidget(label('STAR installs verified upstream files under your local STAR data folder. Your model stays on your PC. Some performance depends on NVIDIA drivers and available VRAM.','Muted'))
        lay.addWidget(card)
        updates=QFrame();updates.setObjectName('PanelCard');ul=QVBoxLayout(updates)
        ul.setContentsMargins(22,20,22,20);ul.setSpacing(12)
        ul.addWidget(label(f'STAR VERSION  {__version__}','Section'))
        ul.addWidget(label('STAR can check GitHub Releases for newer verified versions. New installers upgrade the existing app while preserving your projects and memories.','Muted'))
        self.update_status=label('Currently running v'+__version__,'Status');ul.addWidget(self.update_status)
        self.update_button=button('Check for updates',callback=self.check_star_updates)
        self.update_button.setIcon(qt_icon('refresh'));ul.addWidget(self.update_button)
        self.open_releases_button=button('View STAR releases',callback=lambda:self.open_link(getattr(self,'latest_release_url','https://github.com/oncoursemail/Star-AI/releases/latest')))
        self.open_releases_button.setIcon(qt_icon('github'));ul.addWidget(self.open_releases_button)
        self.install_update_button=button('Install available update',primary=True,callback=self.install_star_update)
        self.install_update_button.setIcon(qt_icon('download','#242116',18))
        self.install_update_button.setEnabled(False);ul.addWidget(self.install_update_button)
        ul.addWidget(label('STAR automatically downloads verified updates from public GitHub Releases. Chats, projects and model files stay safe during upgrades. No GitHub CLI needed.','Small'))
        lay.addWidget(updates)
        lay.addWidget(button('Open STAR local files',callback=self.open_data_folder))
        lay.addStretch(1)
        area.setWidget(content);body.addWidget(area,stretch=1)
        self.pending_update=None
        self.browser_update_required=False
        self.latest_release_url='https://github.com/oncoursemail/Star-AI/releases/latest'
        return page

    def _start_installed_brain(self, info):
        from .desktop_core import query_models
        from .desktop_core import Settings
        from pathlib import Path
        import time
        # Running a saved engine doesn't require LM Studio or Ollama.
        if self.runtime.status() != 'running':
            self.runtime.start(Path(info.executable),Path(info.model),
                app_data()/'logs'/'star-brain.log',port=8080,context=4096,
                gpu_layers=30,projector=Path(info.projector))
        candidate=Settings(endpoint='http://127.0.0.1:8080/v1')
        for _ in range(70):
            if self.runtime.status()!='running':
                raise RuntimeError('STAR Brain stopped unexpectedly. Check the STAR logs folder.')
            try:
                models=query_models(candidate)
                if models:
                    return models[0], info
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError('STAR Brain did not become ready. See %APPDATA%/STAR/logs/star-brain.log')

    def install_star_brain(self):
        from .brain_setup import install_brain
        self.install_brain_button.setEnabled(False)
        self.brain_status.setText('Checking trusted model sources…')
        self.brain_progress.setRange(0,100)
        self.brain_progress.setValue(0)
        self.brain_progress.setFormat('%p% downloaded')
        def work():
            info=install_brain(app_data(), progress=lambda ev: job.event.emit(ev))
            return self._start_installed_brain(info)
        job=Job(work)
        self.jobs.add(job)
        job.event.connect(self.brain_event)
        job.success.connect(self.brain_started)
        job.failure.connect(self.brain_failed)
        job.finished.connect(lambda:self.jobs.discard(job))
        job.start()

    def brain_event(self, event):
        phase=str(event.get('phase','Starting'))
        total=event.get('overall_total') or 0
        loaded=event.get('overall_downloaded') or 0
        if total:
            self.brain_progress.setRange(0,100)
            pct=min(99,int(loaded*100/total))
            self.brain_progress.setValue(pct)
            current=event.get('downloaded') or 0
            self.brain_status.setText(f'{phase}  ·  {pct}%  ·  {loaded/1e9:.2f} / {total/1e9:.2f} GB total')
        else:
            self.brain_status.setText(phase + ('…' if not event.get('finished') else ''))

    def brain_started(self, result):
        model,info=result
        self.brain_progress.setRange(0,100);self.brain_progress.setValue(100);self.brain_progress.setFormat('Ready · 100%')
        self.brain_status.setText('STAR Brain is running locally. You can chat and attach images now!')
        self.install_brain_button.setEnabled(True)
        self.install_brain_button.setText('Brain installed ✓  ·  Restart brain')
        self.side_brain.setText('STAR Brain · Ready')
        self.cfg.endpoint='http://127.0.0.1:8080/v1'
        # With STAR Server selected, the local brain is only a fallback: keep the server model.
        if not uses_star_server(self.cfg):
            self.cfg.model=model
        self.cfg.llama_server=info.executable
        self.cfg.gguf_model=info.model
        self.cfg.save(self.settings_file)
        self.endpoint.setText(self.cfg.endpoint)
        self.model.setCurrentText(model)
        self.llama_server.setText(info.executable)
        self.gguf_model.setText(info.model)
        self.status.setText('STAR is online locally · '+model)
        self.show_page(0)

    def brain_failed(self, message):
        self.install_brain_button.setEnabled(True)
        self.install_brain_button.setText('Try again · Resume Download')
        self.brain_progress.setRange(0,100)
        detail = str(message)
        if 'Not enough free disk space' in detail:
            notice = 'Not enough storage. Free at least 4.5 GB, then choose Try again.'
        elif 'checksum' in detail.lower() or 'SHA-256' in detail:
            notice = 'A downloaded file did not pass the safety check. STAR will download a fresh copy when you retry.'
        elif 'Connect' in detail or 'Timeout' in detail or 'HTTP' in detail:
            notice = 'STAR could not reach its download source. Check your connection and click Try again; partial downloads are saved.'
        elif 'stopped unexpectedly' in detail:
            notice = 'The local AI engine could not start. Please check your NVIDIA driver and STAR logs.'
        else:
            notice = 'Could not finish setup. Click Try again; installed verified files will be reused.\n' + detail[:230]
        self.brain_status.setText(notice)
        self.status.setText('STAR Brain setup paused · You can retry safely')

    def resume_brain(self):
        from .brain_setup import BrainInstall
        info=BrainInstall.load(app_data()/'brain.json')
        if not info:return
        self.brain_status.setText('Resuming local STAR Brain…')
        self.install_brain_button.setEnabled(False)
        job=Job(lambda:self._start_installed_brain(info))
        self.jobs.add(job)
        job.success.connect(self.brain_started)
        job.failure.connect(self.brain_failed)
        job.finished.connect(lambda:self.jobs.discard(job))
        job.start()

    def check_star_updates(self):
        from .updates import get_latest
        self.pending_update=None
        self.update_status.setText('Checking STAR Releases…')
        self.launch_job(get_latest,self.updates_received)

    def updates_received(self,result):
        self.pending_update=None
        self.latest_release_url=result.url
        self.browser_update_required=bool(result.requires_browser)
        if result.requires_browser:
            self.update_status.setText('STAR could not access a public Release. Open GitHub Releases in your browser, download STAR Setup, then select it here. No GitHub CLI needed.')
            self.install_update_button.setText('Select downloaded STAR Setup…')
            self.install_update_button.setEnabled(True)
        elif result.available:
            self.pending_update=result
            self.install_update_button.setText(f'Update to STAR v{result.version}')
            self.install_update_button.setEnabled(True)
            self.update_status.setText(f'New release v{result.version} available!')
        else:
            self.update_status.setText('STAR is up to date · v'+__version__)
            self.install_update_button.setEnabled(False)

    def install_star_update(self):
        from .updates import select_downloaded_installer, stage_installer, launch_installer
        if self.browser_update_required:
            initial=str(Path.home()/'Downloads')
            chosen,_=QFileDialog.getOpenFileName(self,'Select the STAR Setup downloaded from your GitHub Releases page',
                initial,'STAR Setup (STAR-Setup-v*.exe);;Windows installers (*.exe)')
            if not chosen:return
            try:
                candidate=select_downloaded_installer(Path(chosen))
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self,'Not a valid STAR update',str(exc));return
            integrity=('The checksum matches the SHA256SUMS.txt beside it.' if candidate.checksum_verified
                       else 'This executable is unsigned and could not be independently authenticated. Only continue if you downloaded it from your own STAR GitHub Releases page.')
            reply=QMessageBox.question(self,'Install STAR update?',
                f'Install STAR v{candidate.version} over v{__version__}?\n\n{integrity}\n\nSTAR will close while the installer updates it.',
                QMessageBox.Yes | QMessageBox.No,QMessageBox.No)
            if reply != QMessageBox.Yes:return
            try:
                launch_installer(candidate)
            except (OSError, ValueError) as exc:
                self.update_status.setText('Installer could not start: '+str(exc));return
            self.update_status.setText('Starting STAR Setup…')
            self.close()
            return
        if self.pending_update is None:
            self.update_status.setText('Open STAR Releases to download an update.')
            return
        self.install_update_button.setEnabled(False)
        self.update_status.setText('Downloading and verifying the newer STAR Setup…')
        self.launch_job(lambda:stage_installer(self.pending_update,app_data()),self.update_staged)

    def update_staged(self,candidate):
        from .updates import launch_installer
        reply=QMessageBox.question(self,'Verified STAR update',
            f'STAR v{candidate.version} downloaded and checksum-verified. Install now?\n\nSTAR will close, install the update, and restart automatically. Your conversations and models stay saved.',
            QMessageBox.Yes | QMessageBox.No,QMessageBox.Yes)
        if reply != QMessageBox.Yes:
            self.install_update_button.setEnabled(True);return
        try:
            launch_installer(candidate, unattended=True)
        except (OSError, ValueError, PermissionError) as exc:
            self.update_status.setText('Installer could not start: '+str(exc))
            self.install_update_button.setEnabled(True)
            return
        self.update_status.setText('Closing STAR so Setup can replace the old version and restart…')
        self.close()

    def pick_workflow(self):
        selected,_=QFileDialog.getOpenFileName(self,'Select ComfyUI API workflow','','JSON workflows (*.json)')
        if selected:self.comfy_workflow.setText(selected)

    def generate_image(self):
        from .comfy import generate
        path=Path(self.comfy_workflow.text().strip())
        prompt=self.comfy_prompt.toPlainText().strip()
        self.generate_btn.setDisabled(True)
        self.image_status.setText('Generating locally… ensure ComfyUI is running and the language model is unloaded if VRAM is low.')
        self.launch_job(lambda:generate(path,prompt=prompt,node_id=self.comfy_node.text().strip(),
            output=app_data()/'generated',port=self.comfy_port.value()),self.images_received)

    def images_received(self,paths):
        self.generate_btn.setDisabled(False)
        self.image_status.setText('Generated '+str(len(paths))+' image(s) · '+str(paths[0]))
        pixmap=QPixmap(str(paths[0]))
        if not pixmap.isNull():
            self.image_preview.setPixmap(pixmap.scaled(640,320,Qt.KeepAspectRatio,Qt.SmoothTransformation))

    def open_specific_folder(self, folder):
        folder.mkdir(parents=True,exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def create_settings_page(self):
        page=QWidget();body=QVBoxLayout(page);body.setContentsMargins(0,0,0,0);body.setSpacing(0)
        body.addWidget(self.create_header('Settings','Your local models, projects, and tool permissions'))
        area=QScrollArea();area.setWidgetResizable(True)
        content=QWidget();lay=QVBoxLayout(content);lay.setContentsMargins(26,24,26,24);lay.setSpacing(16)
        model_card=QFrame();model_card.setObjectName('PanelCard');fm=QFormLayout(model_card)
        fm.setContentsMargins(18,19,18,19);fm.setSpacing(12)
        fm.addRow(label('LOCAL INFERENCE','Section'))
        self.endpoint=QLineEdit(self.cfg.endpoint)
        fm.addRow('Endpoint (localhost only)',self.endpoint)
        self.model=QComboBox();self.model.setEditable(True)
        self.model.addItem(self.cfg.model)
        fm.addRow('Model identifier',self.model)
        model_controls=QWidget();hl=row(button('Check / list models',callback=self.test_model),button('STAR Brain one-click setup',primary=True,callback=lambda:self.show_page(5)))
        model_controls.setLayout(hl);fm.addRow(model_controls)
        lay.addWidget(model_card)
        local_card=QFrame();local_card.setObjectName('PanelCard');fl=QFormLayout(local_card)
        fl.setContentsMargins(18,19,18,19);fl.setSpacing(12)
        fl.addRow(label('BUILT-IN LOCAL RUNTIME CONTROL','Section'))
        fl.addRow(label('Optional: run llama.cpp from STAR itself. First download the official Windows llama.cpp release and a compatible GGUF model. This does not embed either binary in STAR.','Muted'))
        self.llama_server=QLineEdit(self.cfg.llama_server)
        choose_exe=button('Browse…',callback=self.pick_llama_server)
        chooser=QWidget();chooser.setLayout(row(self.llama_server,choose_exe))
        fl.addRow('llama-server.exe',chooser)
        self.gguf_model=QLineEdit(self.cfg.gguf_model)
        choose_gguf=button('Browse…',callback=self.pick_gguf)
        chooser2=QWidget();chooser2.setLayout(row(self.gguf_model,choose_gguf))
        fl.addRow('GGUF model file',chooser2)
        self.gpu_layers=QSpinBox();self.gpu_layers.setRange(0,1000);self.gpu_layers.setValue(self.cfg.gpu_layers)
        fl.addRow('GPU offload layers',self.gpu_layers)
        self.runtime_status=label('llama.cpp not launched','Status')
        fl.addRow(self.runtime_status)
        launcher=QWidget();launcher.setLayout(row(button('Start local engine',primary=True,callback=self.start_runtime),button('Stop engine',callback=self.stop_runtime),button('llama.cpp downloads',callback=lambda:self.open_link('https://github.com/ggml-org/llama.cpp/releases'))))
        fl.addRow(launcher)
        lay.addWidget(local_card)
        tools_card=QFrame();tools_card.setObjectName('PanelCard');ft=QFormLayout(tools_card)
        ft.setContentsMargins(18,19,18,19);ft.setSpacing(12)
        ft.addRow(label('TOOL ACCESS','Section'))
        self.workspace=QLineEdit(self.cfg.workspace)
        pick=button('Choose…',callback=self.pick_workspace)
        browse=QWidget();hl=row(self.workspace,pick);browse.setLayout(hl)
        ft.addRow('Workspace folder', browse)
        self.edit_workspace=QCheckBox('Allow STAR to modify files inside this folder')
        self.edit_workspace.setChecked(self.cfg.workspace_edit)
        ft.addRow('',self.edit_workspace)
        self.studio_id=QLineEdit(self.cfg.studio_id)
        self.studio_id.setReadOnly(True)
        self.studio_id.setPlaceholderText('Choose an open place from Studio discovery')
        self.studio_target=QComboBox()
        self.studio_target.addItem('This PC · your Studio','local_pc')
        self.studio_target.addItem('Practice Studio · configured host','host_launcher')
        self.studio_target.setCurrentIndex(1 if self.cfg.studio_target=='host_launcher' else 0)
        ft.addRow('Studio connection',self.studio_target)
        ft.addRow('Roblox Studio ID',self.studio_id)
        self.edit_studio=QCheckBox('Allow routine edits in selected disposable Studio place')
        self.edit_studio.setChecked(self.cfg.studio_edit)
        ft.addRow('',self.edit_studio)
        lay.addWidget(tools_card)
        budget_card=QFrame();budget_card.setObjectName('PanelCard');fb=QFormLayout(budget_card)
        fb.setContentsMargins(18,19,18,19);fb.setSpacing(12)
        fb.addRow(label('RESOURCE BUDGET','Section'))
        self.call_budget=QSpinBox();self.call_budget.setRange(1,30);self.call_budget.setValue(self.cfg.max_calls)
        fb.addRow('Maximum model turns',self.call_budget)
        self.context_budget=QSpinBox();self.context_budget.setRange(6000,80000);self.context_budget.setSingleStep(1000);self.context_budget.setValue(self.cfg.context_chars)
        fb.addRow('Approximate context chars',self.context_budget)
        self.reduce_motion=QCheckBox('Reduce animations (simpler motion and fewer transitions)')
        self.reduce_motion.setChecked(self.cfg.reduced_motion)
        fb.addRow('Accessibility',self.reduce_motion)
        lay.addWidget(budget_card)
        save=button('Save STAR settings',primary=True,callback=self.save_settings)
        lay.addWidget(save)
        lay.addWidget(label('The STAR Brain page handles downloading a local model and engine. Advanced manual settings are optional. Roblox Studio and FFmpeg remain separate integrations.','Muted'))
        lay.addStretch(1)
        area.setWidget(content);body.addWidget(area,stretch=1)
        return page

    def launch_job(self, fn, success, *args, **kwargs):
        task=Job(fn,*args,**kwargs)
        self.jobs.add(task)
        task.success.connect(success)
        task.failure.connect(self.job_failed)
        task.finished.connect(lambda: self.jobs.discard(task))
        task.start()

    def job_failed(self, message):
        self.busy=False
        self.thinking_timer.stop()
        self.send.setDisabled(False)
        if hasattr(self,'generate_btn'):self.generate_btn.setDisabled(False)
        self.status.setText('Task failed · ' + message[:170])
        self.append_bubble('event',message)

    def load_chat(self):
        while self.bubbles.count():
            item=self.bubbles.takeAt(0)
            if item.widget():item.widget().deleteLater()
        entries=self.chats.recent(self.cfg.project)
        self.hero.setVisible(not any(role in ('user','assistant') for role,_,_ in entries))
        if not entries:
            self.append_bubble('event','Choose STAR Brain to set up your local AI, then start a conversation. No API key or external chat app required.')
        else:
            for role,body,_ in entries:
                self.append_bubble(role,body)

    def append_bubble(self,who,text):
        outer=QWidget(); h=QHBoxLayout(outer);h.setContentsMargins(0,0,0,0)
        if who=='user':h.addStretch(1)
        b=ChatBubble(who,text)
        if who in ('assistant','user') and hasattr(self,'hero'):
            self.hero.hide()
        h.addWidget(b,stretch=0)
        if who!='user':h.addStretch(1)
        self.bubbles.addWidget(outer)
        if not self.cfg.reduced_motion and len(self.animations) < 10:
            effect=QGraphicsOpacityEffect(outer);outer.setGraphicsEffect(effect)
            animation=QPropertyAnimation(effect,b'opacity',outer)
            animation.setDuration(MOTION_MS['message']);animation.setStartValue(0.05);animation.setEndValue(1.0)
            animation.setEasingCurve(QEasingCurve.OutCubic)
            self.animations.append(animation)
            animation.finished.connect(lambda a=animation:self.animations.remove(a) if a in self.animations else None)
            animation.start()
        QApplication.processEvents()
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def attach(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Attach reference files','','Images/video/audio (*.png *.jpg *.jpeg *.webp *.mp4 *.mov *.mkv *.webm *.wav *.mp3 *.m4a *.flac *.ogg *.aac)')
        for path in paths:
            p=Path(path)
            if p not in self.attachments:
                self.attachments.append(p)
        self.update_attachment_label()

    def update_attachment_label(self):
        if not self.attachments:
            self.file_label.setText('Attach images, audio, or video references (optional)')
            return
        self.file_label.setText('Attached: '+', '.join(p.name for p in self.attachments[-5:])+'  ·  Files processed locally before model input')

    def send_message(self):
        if self.busy:return
        prompt=self.prompt.toPlainText().strip()
        if not prompt:return
        try:
            self.cfg.validate()
        except Exception as exc:
            self.job_failed(str(exc));return
        if not self.cfg.model:
            self.job_failed('Choose a local model in Settings first');return
        self.chats.add(self.cfg.project,'user',prompt)
        self.append_bubble('user',prompt)
        self.prompt.clear();self.busy=True;self.send.setDisabled(True)
        self.status.setText('STAR is thinking…')
        if not self.cfg.reduced_motion:
            self.thinking_timer.start(420)
        incoming=list(self.attachments);self.attachments=[];self.update_attachment_label()
        def work():
            import tempfile
            from .media_features import VIDEO_EXTENSIONS,AUDIO_EXTENSIONS
            pics=[];extra=[]
            with tempfile.TemporaryDirectory(prefix='star-media-') as directory:
                for path in incoming:
                    if path.suffix.lower() in VIDEO_EXTENSIONS:
                        pics+=video_frames(path,Path(directory)/('v_'+uuid.uuid4().hex), max_frames=4)
                        extra.append(f'Video source: {path.name}; sampled 4 frames, not full temporal understanding.')
                    elif path.suffix.lower() in AUDIO_EXTENSIONS:
                        extra.append(f'Audio transcript from {path.name}: '+transcribe_audio(path))
                    else:
                        pics.append(path)
                if len(pics)>4:
                    pics=pics[:4]
                    extra.append('Only first 4 images/frames were supplied due to context limits.')
                text=prompt+'\n\n'+ '\n'.join(extra) if extra else prompt
                # owner_text: only what was typed can become a lesson, never the transcript added above.
                return run_task(self.cfg,text,pics,on_event=lambda ev:self._job.event.emit(ev),owner_text=prompt)
        self._job=Job(work)
        self.jobs.add(self._job)
        self._job.event.connect(self.worker_event)
        self._job.success.connect(self.reply_received)
        self._job.failure.connect(self.job_failed)
        task=self._job
        self._job.finished.connect(lambda: self.jobs.discard(task))
        self._job.start()

    def animate_thinking(self):
        self.thinking_frame=(self.thinking_frame+1)%4
        self.status.setText('STAR is working' + '.' * self.thinking_frame)

    def worker_event(self,ev):
        if ev.get('event')=='tool_finished':
            self.status.setText('STAR used tool: '+str(ev.get('tool','')))
        elif ev.get('event')=='tool_rejected':
            self.status.setText('Tool request rejected by permission policy')
        elif ev.get('event')=='saved':
            self.status.setText('Run saved locally · '+str(ev.get('run_id','')))

    def reply_received(self,answer):
        self.busy=False;self.send.setDisabled(False)
        self.thinking_timer.stop()
        self.last_answer=answer
        self.append_bubble('assistant',answer)
        self.chats.add(self.cfg.project,'assistant',answer)
        self.status.setText('Response saved locally · Open Analytics to view task history')

    def transcribe_attachment(self):
        files=[p for p in self.attachments if p.suffix.lower() in {'.wav','.mp3','.m4a','.flac','.ogg','.aac'}]
        if not files:
            self.job_failed('Attach an audio file to transcribe');return
        self.status.setText('Transcribing locally… (first time may download speech model)')
        self.launch_job(lambda:transcribe_audio(files[0]),self.transcript_received)

    def transcript_received(self,text):
        if text:
            self.prompt.setPlainText((self.prompt.toPlainText()+'\n'+text).strip())
            self.attachments=[p for p in self.attachments if p.suffix.lower() not in {'.wav','.mp3','.m4a','.flac','.ogg','.aac'}]
            self.update_attachment_label()
            self.status.setText('Audio transcribed locally')
        else:self.job_failed('Speech recognizer returned no text')

    def speak_reply(self):
        if not self.last_answer:
            self.job_failed('No STAR response to speak');return
        self.status.setText('Speaking via local voice engine…')
        self.launch_job(lambda:local_speak(self.last_answer),lambda _:self.status.setText('Voice playback completed'))

    def change_project(self):
        chosen=self.project_edit.text().strip()
        if not chosen or chosen==self.cfg.project:return
        self.cfg.project=chosen
        try:self.cfg.save(self.settings_file)
        except Exception as exc:self.job_failed(str(exc));return
        self.load_chat();self.refresh_project_info()

    def select_project(self,item):
        self.project_edit.setText(item.text());self.change_project();self.show_page(0)

    def refresh_project_info(self):
        self.projects_list.clear()
        for name in sorted(set(self.chats.projects()+[self.cfg.project])):
            self.projects_list.addItem(name)
        db=Memory(app_data()/'checkpoints.sqlite3')
        try:self.memory_box.setPlainText(db.get(self.cfg.project) or '(no compacted checkpoint saved yet)')
        finally:db.close()

    def refresh_tool_info(self):
        self.workspace_status.setText('Workspace: '+(self.cfg.workspace or '(not selected)')+'\nWrite permission: '+('On' if self.cfg.workspace_edit else 'Off'))
        from .studio_connections import TARGETS
        self.studio_status.setText(TARGETS[self.cfg.studio_target]+' · MCP not checked · Studio: '+(self.cfg.studio_id or '(not selected)'))

    def discover_studios(self):
        if self.busy:return
        self.studio_status.setText('Connecting to Roblox Studio…')
        self.launch_job(check_studio,self.studios_received,replace(self.cfg))

    def studios_received(self, result):
        if self.busy or result.get('target')!=self.cfg.studio_target:return
        if result.get('state')=='no_instances':
            self.studio_status.setText('STAR local MCP answered · '+str(result['tool_count'])+' tools · no open Studio. Open your place and check the MCP switch.')
            return
        if result.get('state')!='connected':
            self.studio_status.setText('Studio MCP unavailable or no open Studio. Enable it in Assistant → Manage MCP Servers, then test again.')
            return
        choices=result['instances']
        labels=[str(i+1)+'. '+item['name']+' · '+item['id'][:12] for i,item in enumerate(choices)]
        chosen,accepted=QInputDialog.getItem(self,'Select Studio','Choose the open place on this connection:',labels,0,False)
        if not accepted:return
        identifier=choices[labels.index(chosen)]['id']
        current=replace(self.cfg)
        def select():
            import asyncio
            from .studio_connections import select_instance
            return asyncio.run(select_instance(current,identifier))
        self.launch_job(select,self.studio_selected)

    def studio_selected(self,result):
        if self.busy or result.get('target')!=self.cfg.studio_target or not result.get('selected_valid'):return
        self.cfg=replace(self.cfg,studio_id=result['selected_id'],studio_edit=False,studio_luau=False)
        self.cfg.save(self.settings_file)
        self.studio_id.setText(self.cfg.studio_id)
        self.edit_studio.setChecked(False)
        self.studio_status.setText('Studio MCP responded at the last check · selected place · read only')

    def pick_llama_server(self):
        path,_=QFileDialog.getOpenFileName(self,'Select llama-server.exe','','Windows executable (*.exe)')
        if path:self.llama_server.setText(path)

    def pick_gguf(self):
        path,_=QFileDialog.getOpenFileName(self,'Select GGUF file','','GGUF model (*.gguf)')
        if path:self.gguf_model.setText(path)

    def start_runtime(self):
        try:
            args=self.read_ui_settings()
            pid=self.runtime.start(Path(args.llama_server),Path(args.gguf_model),
                app_data()/'logs'/'llama-server.log',port=8080,context=4096,gpu_layers=args.gpu_layers)
            self.endpoint.setText('http://127.0.0.1:8080/v1')
            self.runtime_status.setText(f'Local llama.cpp started · PID {pid} · endpoint 127.0.0.1:8080')
        except Exception as exc:
            self.runtime_status.setText(f'Engine failed: {exc}')

    def stop_runtime(self):
        self.runtime.stop()
        self.runtime_status.setText('Local engine stopped')

    def pick_workspace(self):
        name=QFileDialog.getExistingDirectory(self,'Select local project workspace',self.cfg.workspace or str(Path.home()))
        if name:self.workspace.setText(name)

    def read_ui_settings(self):
        # Start from the saved settings so fields this legacy form does not show
        # (provider, STAR Server address, model roles, connectors) are never wiped.
        new=replace(self.cfg,endpoint=self.endpoint.text().strip(),model=self.model.currentText().strip(),
                     project=self.project_edit.text().strip() or self.cfg.project,
                     workspace=self.workspace.text().strip(),studio_id=self.studio_id.text().strip(),
                     studio_target=self.studio_target.currentData(),
                     workspace_edit=self.edit_workspace.isChecked(),studio_edit=self.edit_studio.isChecked(),
                     max_calls=self.call_budget.value(),context_chars=self.context_budget.value(),
                     llama_server=self.llama_server.text().strip(),gguf_model=self.gguf_model.text().strip(),
                     gpu_layers=self.gpu_layers.value(), reduced_motion=self.reduce_motion.isChecked())
        if new.studio_target!=self.cfg.studio_target:
            new.studio_id='';new.studio_edit=False;new.studio_luau=False
        new.validate();return new

    def save_settings(self):
        if self.busy:
            self.status.setText('Wait for the current task before changing settings')
            return
        try:
            candidate=self.read_ui_settings();candidate.save(self.settings_file)
            previous=self.cfg.project
            self.cfg=candidate
            self.studio_id.setText(candidate.studio_id);self.edit_studio.setChecked(candidate.studio_edit)
            self.status.setText('Settings saved')
            if previous!=self.cfg.project:self.load_chat()
            QMessageBox.information(self,'STAR','Settings saved. No credentials were stored.')
        except Exception as exc:
            QMessageBox.warning(self,'Settings error',str(exc))

    def test_model(self):
        try:candidate=self.read_ui_settings()
        except Exception as exc:
            QMessageBox.warning(self,'Settings error',str(exc));return
        self.status.setText('Checking local model server…')
        self.launch_job(lambda:query_models(candidate),self.models_received)

    def models_received(self,models):
        current=self.model.currentText()
        self.model.clear()
        self.model.addItems(models)
        if current and current not in models:self.model.addItem(current)
        if current:self.model.setCurrentText(current)
        self.status.setText(f'Local model server connected · {len(models)} model(s)')
        QMessageBox.information(self,'Local models','Detected:\n'+('\n'.join(models[:25]) or 'No model currently loaded. Use STAR Brain to install one locally.'))

    def open_data_folder(self):
        app_data().mkdir(parents=True,exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_data())))

    def open_link(self,url):
        QDesktopServices.openUrl(QUrl(url))

    def closeEvent(self,event):
        if self.busy:
            QMessageBox.warning(self,'Task in progress','STAR is still working. Wait for the current task before closing.')
            event.ignore();return
        self.runtime.stop()
        self.chats.close()
        super().closeEvent(event)


def launch():
    # After an upgrade, discard obsolete staged installers only (never chats,
    # memory, model weights, settings or project directories).
    try:
        from .updates import prune_obsolete_update_packages
        prune_obsolete_update_packages(app_data())
    except OSError:
        pass
    app=QApplication(sys.argv)
    app.setApplicationName('STAR Intelligence')
    app.setWindowIcon(qt_icon('star','#ffcf57',64))
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    window=MainWindow()
    window.show()
    sys.exit(app.exec())
