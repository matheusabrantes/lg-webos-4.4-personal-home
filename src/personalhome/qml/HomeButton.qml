import QtQuick 2.4

Item {
    id: root
    property bool selected: false
    property bool card: false
    property bool quiet: false
    property string toolIcon: ""
    property string text: ""
    property string icon: ""
    property int iconSize: 116
    property string family: ""
    property bool imageReady: icon === ""
    property string accessibilityName: text
    signal activated()
    signal pointed()
    signal imageFailed(string path)
    scale: selected && card ? 1.035 : 1
    Accessible.role: Accessible.Button
    Accessible.name: accessibilityName
    Accessible.focused: selected
    Accessible.onPressAction: activated()
    Image {anchors.fill:parent;source:root.card?(root.selected?"assets/card-focused.png":"assets/card.png"):"";smooth:true}
    Rectangle {
        anchors.fill: parent
        anchors.margins: root.selected && root.card ? -4 : 0
        color: root.card ? "transparent" : root.quiet ? (root.selected?"#16323f":"transparent") : root.selected ? "#f3f7f9" : "#ae0e1c26"
        radius: root.card?24:root.quiet?6:34
        border.width: root.selected ? (root.quiet?3:4) : root.quiet?0:1
        border.color: root.selected?"white":(root.card?"#59ffffff":"#7affffff")
    }
    Image {
        id: icon
        width:root.iconSize;height:root.iconSize;anchors.centerIn:parent
        source:root.icon
        fillMode:Image.PreserveAspectFit
        smooth:true
        onStatusChanged: {
            root.imageReady = status === Image.Ready;
            if (status === Image.Error) root.imageFailed(source.toString());
        }
    }
    Image {visible:root.toolIcon!=="inputs";x:root.quiet?8:24;width:27;height:27;anchors.verticalCenter:parent.verticalCenter;source:root.toolIcon&&root.toolIcon!=="inputs" ? "assets/"+root.toolIcon+(root.selected&&!root.quiet?"-dark.png":"-white.png") : "";smooth:true}
    ControlCenterIcon {visible:root.toolIcon==="inputs";x:24;anchors.verticalCenter:parent.verticalCenter;width:28;height:28;ink:root.selected?"#14232c":"white"}
    Text {
        x:root.toolIcon?(root.quiet?43:63):18;anchors.verticalCenter:parent.verticalCenter;text:root.text;textFormat:Text.PlainText
        font.family:root.family;font.pixelSize:26
        color:root.selected&&!root.quiet?"#14232c":"white"
        width:parent.width-x-(root.toolIcon?24:18);elide:Text.ElideRight;horizontalAlignment:root.toolIcon?Text.AlignLeft:Text.AlignHCenter
        visible:root.icon === ""
    }
    MouseArea {anchors.fill:parent;hoverEnabled:true;onEntered:root.pointed();onClicked:root.activated()}
}
