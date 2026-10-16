import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

CheckBox {
    id: control
    property var colors
    hoverEnabled: true
    implicitHeight: 40
    implicitWidth: label.implicitWidth + 48
    spacing: 10
    leftPadding: 0
    rightPadding: 6
    indicator: Rectangle {
        x: 0
        y: (control.height - height) / 2
        width: 30
        height: 18
        radius: 9
        color: control.checked ? control.colors.accent : control.colors.track
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? control.colors.signal : control.checked ? control.colors.accent : control.colors.border_strong
        Rectangle {
            x: control.checked ? 15 : 3
            y: 3
            width: 12
            height: 12
            radius: 6
            color: control.checked ? control.colors.accent_text : control.colors.text_dim
            Behavior on x { NumberAnimation { duration: 100; easing.type: Easing.OutCubic } }
        }
    }
    contentItem: Text {
        id: label
        text: control.text
        leftPadding: 40
        color: control.enabled ? control.colors.text_dim : control.colors.text_faint
        font.family: "Segoe UI"
        font.pixelSize: 12
        verticalAlignment: Text.AlignVCenter
    }
    Accessible.name: text
    ToolTip.visible: hovered && ToolTip.text.length > 0
    ToolTip.delay: 700
}
