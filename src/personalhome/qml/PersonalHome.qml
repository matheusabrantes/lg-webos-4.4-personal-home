import QtQuick 2.4
import "HomeLogic.js" as Logic

FocusScope {
    id: root
    objectName: "personalHome"
    width:1920;height:1080
    property bool homeShown: true
    property bool powerActive: true
    property bool inputAllowed: true
    property string ssid: ""
    property bool launchPending: false
    property bool dialogOpen: false
    property string errorMessage: ""
    property int focusIndex: 0
    property int lastAppIndex: 0
    property var inputEntries: []
    property bool inputLoading: false
    property string inputError: ""
    property double inputMenuRequestedAt: 0
    property int lastInputMenuMs: -1
    readonly property bool inputMenuOpen: inputDropdownLoader.active
    readonly property int inputMenuFocusIndex: inputDropdownLoader.item?inputDropdownLoader.item.currentIndex:-1
    property int iconsReady: 0
    property bool initialFailure: false
    property string clockText: "00:00"
    property string dateText: ""
    property int photoInterval: 600000
    property string photoAssetPrefix: "assets/"
    readonly property bool readyForActivation: !initialFailure && regular.status===FontLoader.Ready && medium.status===FontLoader.Ready && backdrop.ready && iconsReady===6
    readonly property int photoIndex: backdrop.currentIndex
    readonly property int photoCount: Logic.photos.length
    readonly property bool photoLoading: backdrop.loading
    readonly property int photoFailures: backdrop.failedLoads
    readonly property bool timersRunning: photoTimerActive || minute.running
    readonly property bool photoTimerActive: backdrop.cycling
    signal actionRequested(string action)
    signal inputsRequested()
    signal inputChosen(string key)
    signal fatalError(string message)
    visible:homeShown && powerActive
    enabled:inputAllowed
    focus:visible && inputAllowed
    function failed(message) {initialFailure=true;fatalError(message);}
    function countIcons() {
        var count=0;
        for(var n=0;n<6;n++) if(apps.itemAt(n) && apps.itemAt(n).imageReady) count++;
        iconsReady=count;
    }
    function updateClock() {
        var now=Date.now(),parts=Logic.dateParts(now);clockText=parts.time;dateText=parts.date;
        minute.interval=60000-now%60000;
    }
    function completeAction(success,message) {
        launchPending=false;
        if (success) {dialogOpen=false;errorMessage="";}
        else {errorMessage=message||"Não foi possível abrir. Tente novamente.";dialogOpen=true;}
    }
    function requestAction(action) {
        if (!visible || !inputAllowed || !readyForActivation || dialogOpen || (launchPending && action!=="back") || !Logic.allowed(action)) return false;
        if(action==="inputs"){
            inputMenuRequestedAt=Date.now();inputsRequested();inputDropdownLoader.active=true;return true;
        }
        launchPending=true;
        actionRequested(action);
        return true;
    }
    function closeError() {dialogOpen=false;errorMessage="";forceActiveFocus();}
    function focusHome() {if(inputDropdownLoader.item&&inputMenuOpen)inputDropdownLoader.item.forceActiveFocus();else forceActiveFocus();}
    function closeInputs() {inputDropdownLoader.active=false;if(visible&&inputAllowed){focusIndex=6;focusHome();}}
    function prepareHome() {focusIndex=0;completeAction(true,"");if(visible&&inputAllowed)focusHome();}
    function moveFocus(direction) {
        if (!visible || !inputAllowed || dialogOpen) return;
        var centers=[];
        for(var n=0;n<6;n++) centers.push(240+n*288);
        centers.push(tools.x+inputs.width/2);
        centers.push(tools.x+inputs.width+16+wifi.width/2);
        centers.push(tools.x+inputs.width+wifi.width+32+store.width/2);
        centers.push(tools.x+inputs.width+wifi.width+store.width+48+settings.width/2);
        centers.push(1650);
        focusIndex=Logic.move(focusIndex,direction,centers);
    }
    function activate() {
        if(dialogOpen){closeError();return;}
        var action=focusIndex<6?Logic.apps[focusIndex].action:["inputs","wifi","store","settings","original"][focusIndex-6];
        requestAction(action);
    }
    function stepPhoto() {backdrop.nextPhoto();}
    onFocusIndexChanged: if(focusIndex<6)lastAppIndex=focusIndex
    onInputAllowedChanged: {if(!inputAllowed)inputDropdownLoader.active=false;else if(visible&&readyForActivation)focusHome();}
    onHomeShownChanged: {if(!homeShown)inputDropdownLoader.active=false;if(homeShown){updateClock();prepareHome();}}
    onPowerActiveChanged: {if(powerActive&&homeShown){updateClock();prepareHome();}}
    onReadyForActivationChanged: if(readyForActivation && visible && inputAllowed) forceActiveFocus()
    Component.onCompleted: {updateClock();countIcons();if(visible&&inputAllowed)forceActiveFocus();}
    Keys.onPressed: {
        if (!root.visible || !root.inputAllowed) {event.accepted=false;return;}
        if(event.key===Qt.Key_Left){moveFocus("left");event.accepted=true;}
        else if(event.key===Qt.Key_Right){moveFocus("right");event.accepted=true;}
        else if(event.key===Qt.Key_Up){moveFocus("up");event.accepted=true;}
        else if(event.key===Qt.Key_Down){moveFocus("down");event.accepted=true;}
        else if(event.key===Qt.Key_Tab){moveFocus((event.modifiers & Qt.ShiftModifier)?"previous":"next");event.accepted=true;}
        else if(event.key===Qt.Key_Return || event.key===Qt.Key_Enter || event.key===Qt.Key_Space){if(!event.isAutoRepeat)activate();event.accepted=true;}
        else if(event.key===Qt.Key_Escape || event.key===Qt.Key_Back || event.key===Qt.Key_Backspace){if(!event.isAutoRepeat){if(dialogOpen)closeError();else requestAction("back");}event.accepted=true;}
        else event.accepted=false;
    }
    FontLoader {id:regular;source:"assets/google-sans-400.ttf";onStatusChanged:if(status===FontLoader.Error)root.failed("Não foi possível carregar a fonte.")}
    FontLoader {id:medium;source:"assets/google-sans-500.ttf";onStatusChanged:if(status===FontLoader.Error)root.failed("Não foi possível carregar a fonte.")}
    Timer {id:minute;interval:60000;repeat:true;running:root.visible;onTriggered:root.updateClock()}
    Timer {interval:8000;running:root.launchPending&&root.visible&&root.inputAllowed;onTriggered:root.completeAction(false,"O aplicativo não respondeu. Tente novamente.")}
    Item {
        id: design
        width:1920;height:1080;anchors.centerIn:parent
        scale:Math.min(root.width/width,root.height/height)
        PhotoBackdrop {
            id:backdrop;anchors.fill:parent
            cycling:root.visible;interval:root.photoInterval;assetPrefix:root.photoAssetPrefix
            onLoadFailed:if(initial)root.failed("Não foi possível carregar a foto inicial.")
        }
        Rectangle {
            anchors.fill:parent
            gradient:Gradient {
                GradientStop {position:0;color:"#ad040f17"}
                GradientStop {position:0.30;color:"#0f040f17"}
                GradientStop {position:0.48;color:"#00040f17"}
                GradientStop {position:0.64;color:"#38040f17"}
                GradientStop {position:1;color:"#d6040f17"}
            }
        }
        MouseArea {anchors.fill:parent;onClicked:if(root.inputAllowed)root.forceActiveFocus()}
        Text {x:96;y:82;width:360;height:82;text:root.clockText;textFormat:Text.PlainText;color:"white";font.family:regular.name;font.pixelSize:76;font.letterSpacing:-2;verticalAlignment:Text.AlignVCenter}
        Text {x:96;y:171;width:380;height:36;text:root.dateText;textFormat:Text.PlainText;color:"white";font.family:regular.name;font.pixelSize:27;verticalAlignment:Text.AlignVCenter}
        Row {
            id:tools;anchors.right:parent.right;anchors.rightMargin:96;y:100;spacing:16
            HomeButton {
                id:inputs;toolIcon:"inputs";objectName:"inputsButton";width:193;height:64;family:regular.name;selected:root.focusIndex===6;text:"Entradas";accessibilityName:"Escolher entrada"
                onPointed:if(!root.dialogOpen)root.focusIndex=6
                onActivated:root.requestAction("inputs")
            }
            HomeButton {
                id:wifi;toolIcon:"wifi";objectName:"wifiButton";width:Math.max(150,Math.min(240,ssidMeasure.implicitWidth)+87);height:64;family:regular.name;selected:root.focusIndex===7;text:Logic.networkLabel(root.ssid);accessibilityName:"Rede Wi-Fi: "+text
                onPointed:if(!root.dialogOpen)root.focusIndex=7
                onActivated:root.requestAction("wifi")
                Text {id:ssidMeasure;visible:false;text:Logic.networkLabel(root.ssid);textFormat:Text.PlainText;font.family:regular.name;font.pixelSize:26}
            }
            HomeButton {
                id:store;toolIcon:"store";objectName:"storeButton";width:190;height:64;family:regular.name;selected:root.focusIndex===8;text:"LG Store";accessibilityName:"Abrir LG Content Store"
                onPointed:if(!root.dialogOpen)root.focusIndex=8
                onActivated:root.requestAction("store")
            }
            HomeButton {
                id:settings;toolIcon:"settings";objectName:"settingsButton";width:177;height:64;family:regular.name;selected:root.focusIndex===9;text:"Ajustes";accessibilityName:"Abrir ajustes da LG"
                onPointed:if(!root.dialogOpen)root.focusIndex=9
                onActivated:root.requestAction("settings")
            }
        }
        Text {x:96;y:643;width:1100;height:56;text:Logic.apps[root.lastAppIndex].title;textFormat:Text.PlainText;color:"white";font.family:medium.name;font.pixelSize:44;font.weight:Font.Medium;font.letterSpacing:-0.6;verticalAlignment:Text.AlignVCenter}
        Image {x:80;y:726;width:1760;height:226;source:"assets/dock.png";smooth:true}
        Rectangle {x:80;y:726;width:1760;height:226;color:"transparent";radius:38;border.width:1;border.color:"#80ffffff"}
        Repeater {
            id:apps;model:Logic.apps
            onItemAdded:root.countIcons()
            HomeButton {
                objectName:"appButton"+index
                x:108+index*288;y:755;width:264;height:168;card:true
                icon:"assets/"+modelData.icon;iconSize:modelData.size;family:regular.name
                accessibilityName:"Abrir "+modelData.title
                selected:root.focusIndex===index
                onImageReadyChanged:root.countIcons()
                onImageFailed:root.failed("Não foi possível carregar um ícone.")
                onPointed:if(!root.dialogOpen)root.focusIndex=index
                onActivated:root.requestAction(modelData.action)
            }
        }
        Row {
            anchors.right:parent.right;anchors.rightMargin:96;y:990;height:36;spacing:32
            Text {height:36;text:"◇  Navegar";textFormat:Text.PlainText;color:"white";font.family:regular.name;font.pixelSize:24;verticalAlignment:Text.AlignVCenter}
            Text {height:36;text:"OK  Abrir";textFormat:Text.PlainText;color:"white";font.family:regular.name;font.pixelSize:24;verticalAlignment:Text.AlignVCenter}
            HomeButton {
                id:original;quiet:true;toolIcon:"back";objectName:"originalButton";width:252;height:36;text:"Home da LG";family:regular.name;selected:root.focusIndex===10;accessibilityName:"Voltar à Home original da LG"
                onPointed:if(!root.dialogOpen)root.focusIndex=10
                onActivated:root.requestAction("original")
            }
        }
        MouseArea {anchors.fill:parent;visible:root.inputMenuOpen;z:3;hoverEnabled:true;onClicked:root.closeInputs()}
        Loader {
            id:inputDropdownLoader;objectName:"inputDropdownLoader";z:4;x:tools.x;y:tools.y+tools.height+12
            active:false;source:"InputDropdown.qml"
            onLoaded:{item.family=regular.name;item.open();root.lastInputMenuMs=Date.now()-root.inputMenuRequestedAt;}
            onStatusChanged:if(status===Loader.Error){active=false;root.completeAction(false,"Não foi possível abrir as entradas.");}
        }
        Binding {target:inputDropdownLoader.item;property:"entries";value:root.inputEntries;when:inputDropdownLoader.item!==null}
        Binding {target:inputDropdownLoader.item;property:"loading";value:root.inputLoading;when:inputDropdownLoader.item!==null}
        Binding {target:inputDropdownLoader.item;property:"errorMessage";value:root.inputError;when:inputDropdownLoader.item!==null}
        Connections {
            target:inputDropdownLoader.item
            onChosen:root.inputChosen(entry.key)
            onDismissed:root.closeInputs()
            onHandledKey:if(typeof root.diagnosticKeyCount==="number"){root.diagnosticKeyCount++;root.diagnosticLastKey=key;}
        }
        Rectangle {
            anchors.fill:parent;visible:root.dialogOpen;color:"#cc040f17";z:5
            MouseArea {anchors.fill:parent;onClicked: {}}
            Rectangle {
                width:720;height:330;anchors.centerIn:parent;radius:16;color:"#152c36";border.width:1;border.color:"#46616d"
                Text {x:44;y:36;width:632;text:"Não foi possível abrir";textFormat:Text.PlainText;color:"white";font.family:medium.name;font.pixelSize:40}
                Text {x:44;y:106;width:632;height:110;text:root.errorMessage;textFormat:Text.PlainText;wrapMode:Text.Wrap;color:"#edf3f5";font.family:regular.name;font.pixelSize:27}
                HomeButton {x:44;y:240;width:160;height:60;text:"Voltar";family:regular.name;selected:true;onActivated:root.closeError()}
            }
        }
    }
}
