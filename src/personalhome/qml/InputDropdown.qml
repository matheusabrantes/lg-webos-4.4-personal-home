import QtQuick 2.4

FocusScope {
    id: menu
    objectName: "inputDropdown"
    property var entries: []
    property string family: ""
    property int currentIndex: 0
    property int rowHeight: 64
    property bool loading:false
    property string errorMessage:""
    readonly property int entryCount:list.count
    signal chosen(var entry)
    signal dismissed()
    signal handledKey(int key)
    width: 390
    height: 54 + Math.max(1,Math.min(6,entryCount)) * rowHeight + 14
    visible: false
    enabled:visible
    Accessible.role: Accessible.PopupMenu
    Accessible.name: "Entradas"
    property string focusedKey:""
    onEntriesChanged:{var found=-1;for(var i=0;i<(entries||[]).length;i++)if(entries[i].key===focusedKey)found=i;currentIndex=found>=0?found:Math.max(0,Math.min(currentIndex,entryCount-1));}
    onCurrentIndexChanged:if(entries&&entries[currentIndex])focusedKey=entries[currentIndex].key

    function open() {
        currentIndex=0;
        focusedKey=entries.length?entries[0].key:"";
        visible=true;
        forceActiveFocus();
        list.positionViewAtIndex(currentIndex,ListView.Contain);
    }
    function close() { visible=false; dismissed(); }
    function move(delta) {
        currentIndex=Math.max(0,Math.min(entryCount-1,currentIndex+delta));
        list.positionViewAtIndex(currentIndex,ListView.Contain);
    }
    function choose() {
        var entry=entries[currentIndex];
        if(!entry || entry.enabled===false)return;
        visible=false;
        chosen(entry);
        dismissed();
    }
    Keys.onPressed: {
        if(!menu.visible){event.accepted=false;return;}
        handledKey(event.key);
        if(event.key===Qt.Key_Up)move(-1);
        else if(event.key===Qt.Key_Down)move(1);
        else if(event.key===Qt.Key_Return || event.key===Qt.Key_Enter || event.key===Qt.Key_Space){if(!event.isAutoRepeat)choose();}
        else if(event.key===Qt.Key_Escape || event.key===Qt.Key_Back || event.key===Qt.Key_Backspace){if(!event.isAutoRepeat)close();}
        event.accepted=true;
    }
    Rectangle {
        anchors.fill:parent;radius:20;color:"#f0d8dddf";border.width:1;border.color:"#c9ffffff"
    }
    Text {
        x:22;y:16;text:"Entradas";textFormat:Text.PlainText;color:"#37464d"
        font.family:menu.family;font.pixelSize:21;font.weight:Font.Medium
    }
    Text {
        anchors.right:parent.right;anchors.rightMargin:22;y:18
        text:menu.loading?"Atualizando…":menu.errorMessage?"Atualização indisponível":"";textFormat:Text.PlainText
        color:"#37464d";font.family:menu.family;font.pixelSize:16
    }
    ListView {
        id:list;objectName:"inputDropdownList";x:10;y:54;width:parent.width-20;height:parent.height-y-14
        model:menu.entries;clip:true;boundsBehavior:Flickable.StopAtBounds
        delegate:Item {
            id:row;width:list.width;height:menu.rowHeight
            readonly property bool selected:menu.currentIndex===index
            readonly property bool unavailable:modelData.enabled===false
            Accessible.role:Accessible.MenuItem
            Accessible.name:modelData.label+(modelData.status?", "+modelData.status:"")
            Accessible.focused:selected
            enabled:!unavailable
            Accessible.onPressAction:{menu.currentIndex=index;menu.choose();}
            Rectangle {
                x:0;y:3;width:parent.width;height:parent.height-6;radius:11
                color:row.selected?"#304a56":"transparent"
            }
            Image {
                x:16;anchors.verticalCenter:parent.verticalCenter;width:28;height:28
                opacity:row.unavailable?.45:1
                source:"assets/dropdown-"+modelData.kind+"-"+(row.selected?"white":modelData.disconnected?"gray":"dark")+".png"
                fillMode:Image.PreserveAspectFit;smooth:true
            }
            Text {
                x:60;anchors.verticalCenter:parent.verticalCenter;width:modelData.status?190:270
                text:modelData.label;textFormat:Text.PlainText;elide:Text.ElideRight
                color:row.selected?"white":row.unavailable||modelData.disconnected?"#59696f":"#172b34"
                font.family:menu.family;font.pixelSize:27
            }
            Text {
                anchors.right:parent.right;anchors.rightMargin:44;anchors.verticalCenter:parent.verticalCenter;width:92
                text:modelData.status||"";textFormat:Text.PlainText;horizontalAlignment:Text.AlignRight;elide:Text.ElideRight
                color:row.selected?"#e4edf0":"#59696f";font.family:menu.family;font.pixelSize:18
            }
            Text {
                anchors.right:parent.right;anchors.rightMargin:16;anchors.verticalCenter:parent.verticalCenter
                text:modelData.current?"✓":"";textFormat:Text.PlainText;color:row.selected?"white":"#304a56"
                font.family:menu.family;font.pixelSize:26
            }
            Rectangle {x:16;y:0;width:parent.width-32;height:1;color:"#2430444d";visible:modelData.kind==="usb"}
            MouseArea {
                anchors.fill:parent;hoverEnabled:true
                onEntered:menu.currentIndex=index
                onClicked:{menu.currentIndex=index;menu.choose();}
            }
        }
    }
    Text {
        x:22;y:70;width:parent.width-44;text:"Nenhuma entrada disponível";textFormat:Text.PlainText
        visible:!menu.entryCount;color:"#37464d";font.family:menu.family;font.pixelSize:23
    }
    Rectangle {
        x:parent.width-6;y:58;width:3;radius:1.5;color:"#4c304a56"
        visible:list.contentHeight>list.height
        height:Math.max(24,list.height*list.height/list.contentHeight)
    }
}
