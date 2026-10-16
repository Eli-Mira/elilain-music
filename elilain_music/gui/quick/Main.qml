import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: root
    required property var backend
    readonly property var p: backend.palette
    readonly property var prefs: backend.preferences
    width: 1340
    height: 940
    minimumWidth: 1120
    minimumHeight: 820
    visible: true
    title: "EliLain-Music · Wired Sound Terminal"
    color: p.bg_top
    font.family: "Segoe UI"
    font.pixelSize: 13
    onClosing: function(close) { close.accepted = backend.requestClose() }

    Connections {
        target: backend
        function onSafeToClose() { root.close() }
    }
    Shortcut { sequence: "Ctrl+L"; onActivated: { source.forceActiveFocus(); source.selectAll() } }
    Shortcut { sequence: "Ctrl+Return"; enabled: !backend.busy; onActivated: backend.startDownload(source.text) }
    Shortcut { sequence: "Ctrl+T"; onActivated: backend.toggleTheme() }
    Shortcut { sequence: "Escape"; enabled: backend.busy; onActivated: backend.stop() }

    FolderDialog {
        id: folderDialog
        title: "Choose your music archive folder"
        onAccepted: backend.chooseDestination(selectedFolder)
    }

    component Micro: Text {
        color: root.p.text_faint
        font.family: "Consolas"
        font.pixelSize: 11
        font.letterSpacing: 1
        elide: Text.ElideRight
    }
    component Panel: Rectangle {
        radius: 14
        color: root.p.surface
        border.color: root.p.border
        border.width: 1
    }
    component Hairline: Rectangle {
        color: root.p.border
        implicitHeight: 1
        Layout.fillWidth: true
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 24

        // The square reference stays intact, not stretched into a generic avatar.
        Panel {
            Layout.preferredWidth: 270
            Layout.fillHeight: true
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: root.height < 880 ? 16 : 20
                spacing: root.height < 880 ? 9 : 11
                RowLayout {
                    Layout.fillWidth: true
                    Micro { text: "SERIAL EXPERIMENTS"; color: root.p.accent; Layout.fillWidth: true }
                    Rectangle { width: 6; height: 6; radius: 3; color: root.p.signal }
                }
                Text {
                    text: "lain."
                    color: root.p.text
                    font.family: "Georgia"
                    font.pixelSize: root.height < 880 ? 62 : 70
                    font.letterSpacing: -3
                    lineHeight: 0.95
                }
                Micro { text: "岩倉玲音 / IWAKURA LAIN"; font.letterSpacing: 0.5 }
                Rectangle {
                    id: portraitFrame
                    objectName: "portraitFrame"
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.height < 880 ? width - 28 : width
                    color: "#000000"
                    radius: 8
                    clip: true
                    Image {
                        objectName: "lainPortrait"
                        anchors.fill: parent
                        source: backend.artworkBase + "lain.png"
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                        Accessible.name: "Eli's cyan portrait of Lain Iwakura at a monitor"
                    }
                    Repeater {
                        model: root.prefs.crt_motion ? Math.ceil(portraitFrame.height / 4) : 0
                        Rectangle { required property int index; width: portraitFrame.width; height: 1; y: index * 4; color: "#18000000" }
                    }
                    Rectangle {
                        width: parent.width
                        height: 2
                        color: "#18ffffff"
                        visible: root.prefs.crt_motion
                        NumberAnimation on y {
                            from: 0; to: portraitFrame.height
                            duration: 25000
                            loops: Animation.Infinite
                            running: root.prefs.crt_motion && root.visible
                        }
                    }
                    Rectangle { anchors.fill: parent; color: "transparent"; radius: 8; border.color: "#1affffff" }
                }
                Micro { text: "REAL WORLD  ↔  WIRED"; color: root.p.signal }
                Image {
                    objectName: "wiredScene"
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.height < 880 ? 108 : 139
                    source: backend.artworkBase + "wired-city.png"
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    Accessible.name: "Lain at Nakano in a blue ruined city"
                    Rectangle { anchors.fill: parent; color: "transparent"; border.color: "#1affffff" }
                }
                Hairline {}
                Text {
                    text: "A quiet place\nfor your music."
                    color: root.p.text
                    font.pixelSize: 19
                    lineHeight: 1.2
                }
                Text {
                    text: "Saved here. Not in the cloud.\nNo account. No API keys."
                    color: root.p.text_dim
                    font.pixelSize: 12
                    lineHeight: 1.5
                }
                Item { Layout.fillHeight: true; Layout.minimumHeight: 8 }
                SignalToggle {
                    objectName: "motionToggle"
                    colors: root.p
                    text: "CRT motion"
                    checked: root.prefs.crt_motion
                    onClicked: backend.setPreference("crt_motion", checked)
                    ToolTip.text: "Optional scanlines, only on the portrait. Off means a still image."
                }
                Hairline {}
                Micro { text: "PERSONAL FAN INTERFACE"; font.pixelSize: 10; font.letterSpacing: 0.5 }
                Text {
                    objectName: "artCredit"
                    text: root.height < 880 ? "Artwork © respective rights holders." : "Artwork supplied by Eli.\n© respective rights holders."
                    color: root.p.text_faint
                    font.pixelSize: 11
                    lineHeight: 1.4
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 5
                    Micro { text: "LAYER : 01  /  SOUND TERMINAL"; color: root.p.signal }
                    Text { text: "EliLain / Music"; color: root.p.text; font.pixelSize: 32; font.weight: Font.DemiBold; font.letterSpacing: -1; Layout.fillWidth: true }
                }
                SignalButton {
                    objectName: "themeButton"
                    colors: root.p
                    text: root.prefs.theme === "dark" ? "Real World" : "Wired"
                    shortcutText: "Ctrl T"
                    onClicked: backend.toggleTheme()
                    ToolTip.text: "Switch light / dark · Ctrl+T"
                }
                SignalButton { objectName: "folderButton"; colors: root.p; text: "Open folder"; onClicked: backend.openFolder() }
            }

            // Keep both hands and the complete original composition visible.
            Rectangle {
                objectName: "wiredBanner"
                Layout.fillWidth: true
                Layout.preferredHeight: root.height < 880 ? 132 : 164
                radius: 12
                color: "#000000"
                border.color: root.p.border
                clip: true
                Image {
                    objectName: "bannerImage"
                    anchors.fill: parent
                    anchors.margins: 1
                    source: backend.artworkBase + "wired-banner.png"
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    Accessible.name: "Cyan and magenta hands reaching across the Wired"
                }
            }

            Panel {
                Layout.fillWidth: true
                Layout.preferredHeight: sourceColumn.implicitHeight + 36
                ColumnLayout {
                    id: sourceColumn
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        Micro { text: "01 / SOURCE CONNECTION"; color: root.p.text_dim; Layout.fillWidth: true }
                        Micro { text: "YOUTUBE · SOUNDCLOUD · SPOTIFY"; font.pixelSize: 10; font.letterSpacing: 0.2 }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        TextField {
                            id: source
                            objectName: "sourceInput"
                            Layout.fillWidth: true
                            implicitHeight: 48
                            placeholderText: "Paste a music link, or search artist + song…"
                            color: root.p.text
                            placeholderTextColor: root.p.text_faint
                            selectionColor: root.p.accent
                            selectedTextColor: root.p.accent_text
                            font.pixelSize: 14
                            leftPadding: 14
                            rightPadding: 14
                            selectByMouse: true
                            onAccepted: backend.startDownload(text)
                            Accessible.name: "Music link or artist and song search"
                            background: Rectangle {
                                color: root.p.bg_bottom
                                radius: 8
                                border.width: source.activeFocus ? 2 : 1
                                border.color: source.activeFocus ? root.p.accent : root.p.border
                            }
                        }
                        SignalButton {
                            objectName: "downloadButton"
                            colors: root.p
                            variant: "primary"
                            text: backend.busy ? "Transferring…" : "Download"
                            shortcutText: "Enter"
                            enabled: !backend.busy
                            onClicked: backend.startDownload(source.text)
                            ToolTip.text: "Download the music link or search · Enter / Ctrl+Enter"
                        }
                        SignalButton {
                            objectName: "stopButton"
                            colors: root.p
                            variant: "danger"
                            text: "Stop"
                            shortcutText: "Esc"
                            enabled: backend.busy
                            onClicked: backend.stop()
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12
                        ColumnLayout {
                            spacing: 4
                            Micro { text: "AUDIO FORMAT"; font.pixelSize: 10; font.letterSpacing: 0.8 }
                            ComboBox {
                                id: quality
                                objectName: "qualityControl"
                                Layout.preferredWidth: 200
                                implicitHeight: 40
                                model: ["Low · Opus", "Medium · Opus", "High · MP3", "Best · source codec", "FLAC · converted"]
                                property var values: ["low", "medium", "high", "best", "lossless"]
                                currentIndex: values.indexOf(root.prefs.quality)
                                onActivated: backend.setPreference("quality", values[currentIndex])
                                leftPadding: 12
                                rightPadding: 30
                                Accessible.name: "Audio format and quality preset"
                                contentItem: Text { text: quality.displayText; color: root.p.text; font.pixelSize: 12; verticalAlignment: Text.AlignVCenter }
                                indicator: Canvas {
                                    x: quality.width - width - 12
                                    y: (quality.height - height) / 2
                                    width: 10; height: 6
                                    property color ink: root.p.text_dim
                                    onInkChanged: requestPaint()
                                    onPaint: {
                                        var ctx = getContext("2d")
                                        ctx.clearRect(0, 0, width, height)
                                        ctx.strokeStyle = ink
                                        ctx.lineWidth = 1.5
                                        ctx.beginPath(); ctx.moveTo(1, 1); ctx.lineTo(5, 5); ctx.lineTo(9, 1); ctx.stroke()
                                    }
                                }
                                background: Rectangle { color: root.p.surface_alt; radius: 6; border.width: quality.activeFocus ? 2 : 1; border.color: quality.activeFocus ? root.p.signal : root.p.border }
                                delegate: ItemDelegate {
                                    width: quality.width
                                    height: 40
                                    required property string modelData
                                    required property int index
                                    text: modelData
                                    highlighted: quality.highlightedIndex === index
                                    contentItem: Text { text: modelData; color: root.p.text; font.pixelSize: 12; verticalAlignment: Text.AlignVCenter }
                                    background: Rectangle { color: highlighted ? root.p.track : root.p.surface }
                                }
                                popup: Popup {
                                    y: quality.height + 6
                                    width: quality.width
                                    padding: 4
                                    implicitHeight: contentItem.implicitHeight + 8
                                    contentItem: ListView { clip: true; implicitHeight: contentHeight; model: quality.popup.visible ? quality.delegateModel : null; currentIndex: quality.highlightedIndex }
                                    background: Rectangle { color: root.p.surface; radius: 8; border.color: root.p.border_strong }
                                }
                            }
                        }
                        ColumnLayout {
                            spacing: 4
                            Micro { text: "FRAGMENTS"; font.pixelSize: 10; font.letterSpacing: 0.8 }
                            SpinBox {
                                id: fragments
                                objectName: "fragmentControl"
                                from: 1; to: 16
                                value: root.prefs.fragments
                                onValueModified: backend.setPreference("fragments", value)
                                implicitWidth: 94
                                implicitHeight: 40
                                Accessible.name: "Network fragments"
                                contentItem: Text { text: fragments.value; color: root.p.text; font.family: "Consolas"; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                                background: Rectangle { color: root.p.surface_alt; radius: 6; border.width: fragments.activeFocus ? 2 : 1; border.color: fragments.activeFocus ? root.p.signal : root.p.border }
                                up.indicator: Rectangle { x: fragments.width - width; width: 26; height: fragments.height; color: fragments.up.pressed ? root.p.track : "transparent"; Text { anchors.centerIn: parent; text: "+"; color: root.p.text_dim; font.pixelSize: 18 } }
                                down.indicator: Rectangle { width: 26; height: fragments.height; color: fragments.down.pressed ? root.p.track : "transparent"; Text { anchors.centerIn: parent; text: "−"; color: root.p.text_dim; font.pixelSize: 18 } }
                            }
                        }
                        Item { Layout.fillWidth: true }
                        SignalToggle { colors: root.p; text: "Tags"; checked: root.prefs.embed_metadata; onClicked: backend.setPreference("embed_metadata", checked) }
                        SignalToggle { colors: root.p; text: "Cover"; checked: root.prefs.embed_thumbnail; onClicked: backend.setPreference("embed_thumbnail", checked) }
                        SignalToggle { colors: root.p; text: "Replace"; checked: root.prefs.overwrite; onClicked: backend.setPreference("overwrite", checked); ToolTip.text: "Overwrite files already in the archive" }
                    }
                    Hairline {}
                    RowLayout {
                        Layout.fillWidth: true
                        Micro { text: "ARCHIVE"; color: root.p.signal; font.letterSpacing: 0.5 }
                        Text { text: root.prefs.output_dir; color: root.p.text_dim; font.pixelSize: 12; elide: Text.ElideMiddle; Layout.fillWidth: true; ToolTip.visible: pathHover.hovered; ToolTip.text: text; HoverHandler { id: pathHover } }
                        SignalButton { objectName: "destinationButton"; colors: root.p; text: "Change folder"; implicitHeight: 34; onClicked: folderDialog.open() }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: errorLine.implicitHeight + 24
                visible: backend.error.length > 0
                color: root.p.surface_alt
                radius: 10
                border.color: root.p.err
                RowLayout {
                    id: errorLine
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 10
                    Text { text: "!"; color: root.p.err; font.pixelSize: 16; font.bold: true }
                    Text { text: backend.error; color: root.p.err; wrapMode: Text.Wrap; font.pixelSize: 12; Layout.fillWidth: true; Accessible.name: "Download error: " + text }
                    SignalButton { colors: root.p; text: "Dismiss"; implicitHeight: 32; onClicked: backend.dismissError() }
                }
            }

            Panel {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 180
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 12
                    RowLayout {
                        Layout.fillWidth: true
                        Micro { text: "02 / TRANSFER QUEUE"; color: root.p.text_dim; Layout.fillWidth: true }
                        Micro { text: backend.jobs.length ? backend.jobs.length + " CONNECTION" + (backend.jobs.length === 1 ? "" : "S") : "STANDING BY"; color: root.p.signal; font.letterSpacing: 0.5 }
                    }
                    Item {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend.jobs.length === 0
                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 8
                            Text { text: "[  no signal yet  ]"; font.family: "Consolas"; font.pixelSize: 18; color: root.p.text_dim; Layout.alignment: Qt.AlignHCenter }
                            Text { text: "Your next song starts with a connection."; font.pixelSize: 12; color: root.p.text_faint; Layout.alignment: Qt.AlignHCenter }
                            SignalButton { colors: root.p; text: "Paste a music link"; shortcutText: "Ctrl L"; Layout.alignment: Qt.AlignHCenter; onClicked: { source.forceActiveFocus(); source.selectAll() } ToolTip.text: "Focus the source field · Ctrl+L" }
                        }
                    }
                    ListView {
                        id: queue
                        objectName: "transferQueue"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        visible: backend.jobs.length > 0
                        clip: true
                        model: backend.jobs
                        spacing: 8
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { }
                        delegate: Rectangle {
                            id: transfer
                            required property var modelData
                            width: queue.width
                            height: rowContent.implicitHeight + 24
                            radius: 9
                            color: root.p.surface_alt
                            border.color: root.p.border
                            readonly property color stateColor: modelData.state === "done" ? root.p.ok : modelData.state === "error" ? root.p.err : modelData.state === "cancelled" ? root.p.warn : root.p.accent
                            ColumnLayout {
                                id: rowContent
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 8
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text { text: transfer.modelData.title; color: root.p.text; font.pixelSize: 13; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true; ToolTip.visible: rowHover.hovered; ToolTip.text: text; HoverHandler { id: rowHover } }
                                    Text { text: transfer.modelData.status; color: transfer.stateColor; font.pixelSize: 11; font.weight: Font.DemiBold }
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 3
                                    radius: 2
                                    color: root.p.track
                                    Rectangle { height: parent.height; width: parent.width * transfer.modelData.percent / 100; radius: 2; color: transfer.stateColor; Behavior on width { NumberAnimation { duration: 120 } } }
                                }
                                Text { text: transfer.modelData.detail; color: root.p.text_faint; font.family: "Consolas"; font.pixelSize: 11; elide: Text.ElideRight; Layout.fillWidth: true }
                            }
                        }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: backend.message; color: root.p.text_faint; font.pixelSize: 11; elide: Text.ElideRight; Layout.fillWidth: true }
                        SignalButton { objectName: "clearButton"; colors: root.p; text: "Clear finished"; implicitHeight: 34; onClicked: backend.clearFinished() }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Micro { text: "LOCAL ARCHIVE / NO CLOUD"; color: root.p.text_dim; font.pixelSize: 10; font.letterSpacing: 0.6; Layout.fillWidth: true }
                Micro { text: "yt-dlp " + backend.engineVersion; font.pixelSize: 10; font.letterSpacing: 0 }
                Rectangle { width: 4; height: 4; radius: 2; color: root.p.border_strong }
                Micro { text: backend.ffmpegAvailable ? "ffmpeg ready" : "ffmpeg missing"; color: backend.ffmpegAvailable ? root.p.ok : root.p.err; font.pixelSize: 10; font.letterSpacing: 0 }
            }
        }
    }
}
