import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: control
    property var colors
    property string variant: "secondary"
    property string shortcutText: ""
    property bool animate: true
    readonly property bool primary: variant === "primary"
    readonly property color foreground: !enabled ? colors.text_faint : primary ? colors.accent_text : variant === "danger" ? colors.err : colors.text
    implicitHeight: 44
    implicitWidth: contents.implicitWidth + 32
    leftPadding: 16
    rightPadding: 16
    topPadding: 8
    bottomPadding: 8
    hoverEnabled: true
    font.family: "Segoe UI"
    font.pixelSize: 13
    font.weight: Font.DemiBold
    scale: down ? 0.96 : 1
    Behavior on scale { NumberAnimation { duration: control.animate ? 90 : 0; easing.type: Easing.OutCubic } }
    background: Rectangle {
        radius: 8
        color: !control.enabled ? control.colors.surface_alt : control.primary ? (control.down ? control.colors.accent_press : control.hovered ? control.colors.accent_hover : control.colors.accent) : (control.down ? control.colors.border : control.hovered ? control.colors.track : control.colors.surface_alt)
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? control.colors.signal : control.primary ? control.colors.accent : control.variant === "danger" && control.enabled ? control.colors.err : control.hovered ? control.colors.border_strong : control.colors.border
        Behavior on color { ColorAnimation { duration: control.animate ? 120 : 0 } }
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
            height: 1
            color: Qt.rgba(1,1,1,control.primary ? 0.25 : 0.08)
        }
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 2 }
            height: 2
            radius: 1
            color: Qt.rgba(0,0,0,control.down ? 0 : 0.2)
        }
    }
    contentItem: RowLayout {
        id: contents
        spacing: 12
        Text {
            text: control.text
            color: control.foreground
            font: control.font
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        Rectangle {
            visible: control.shortcutText.length > 0
            implicitWidth: key.implicitWidth + 12
            implicitHeight: 23
            radius: 4
            color: control.primary ? Qt.rgba(0,0,0,0.07) : control.colors.bg_bottom
            border.color: control.primary ? Qt.rgba(0,0,0,0.18) : control.colors.border_strong
            border.width: 1
            Text {
                id: key
                anchors.centerIn: parent
                text: control.shortcutText
                color: control.foreground
                opacity: 0.8
                font.family: "Consolas"
                font.pixelSize: 11
                font.weight: Font.Normal
            }
        }
    }
    ToolTip.visible: hovered && ToolTip.text.length > 0
    ToolTip.delay: 700
    Accessible.name: text
}
