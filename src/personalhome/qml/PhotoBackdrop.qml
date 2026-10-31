import QtQuick 2.4
import "HomeLogic.js" as Logic

Item {
    id: root
    objectName: "photoBackdrop"
    clip: true
    property bool cycling: false
    property int interval: 600000
    property int currentIndex: 0
    property bool usingFirst: true
    property bool loading: false
    property bool ready: false
    property int failedLoads: 0
    property int pendingIndex: -1
    property double nextChangeAt: 0
    property bool hasBeenShown: false
    property string assetPrefix: "assets/"
    signal loadFailed(string path, bool initial)
    Component.onCompleted: first.source = root.assetPrefix + Logic.photos[0].file
    function scheduleRotation() {
        rotation.stop();
        if (!cycling || !ready || loading) return;
        if (!nextChangeAt) nextChangeAt = Date.now() + interval;
        rotation.interval = Math.max(1, nextChangeAt - Date.now());
        rotation.start();
    }
    function nextPhoto() {
        loadPhoto((currentIndex+1)%Logic.photos.length);
    }
    function resumeCycle() {
        rotation.stop();
        if (!cycling || !ready) return;
        if (!hasBeenShown) {
            hasBeenShown=true;
            nextChangeAt=Date.now()+interval;
            scheduleRotation();
            return;
        }
        var elapsed=Math.max(1,Math.floor((Date.now()-nextChangeAt)/interval)+1);
        var advance=elapsed%Logic.photos.length || 1;
        loadPhoto((currentIndex+advance)%Logic.photos.length);
    }
    function loadPhoto(index) {
        if (!cycling || loading || !ready) return;
        pendingIndex = index;
        var target = usingFirst ? second : first;
        target.position = Logic.photos[pendingIndex].position;
        loading = true;
        target.source = assetPrefix + Logic.photos[pendingIndex].file;
    }
    function loaded(slot) {
        if (slot.status === Image.Error) {
            failedLoads++;
            loadFailed(slot.source.toString(), !ready);
            if (loading) {slot.source="";loading=false;pendingIndex=-1;}
            nextChangeAt = Date.now() + interval;
            scheduleRotation();
        } else if (slot.status === Image.Ready) {
            if (!ready) {ready=true;resumeCycle();return;}
            if (!loading || slot === (usingFirst ? first : second)) return;
            if (cycling) {
                var previous = usingFirst ? first : second;
                currentIndex = pendingIndex;
                usingFirst = !usingFirst;
                previous.source = "";
            } else slot.source = "";
            loading=false;pendingIndex=-1;
            nextChangeAt = Date.now() + interval;
            scheduleRotation();
        }
    }
    onCyclingChanged: resumeCycle()
    onIntervalChanged: {nextChangeAt=Date.now()+interval;scheduleRotation();}
    Image {
        id: first
        objectName:"photoFirst"
        property real position: Logic.photos[0].position
        source: ""
        asynchronous: true
        cache: false
        smooth: true
        width: Math.max(root.width,root.height*(Math.max(1,implicitWidth)/Math.max(1,implicitHeight)))
        height: Math.max(root.height,root.width/(Math.max(1,implicitWidth)/Math.max(1,implicitHeight)))
        x: (root.width-width)/2
        y: (root.height-height)*position
        visible: root.usingFirst
        onStatusChanged: root.loaded(first)
    }
    Image {
        id: second
        objectName:"photoSecond"
        property real position: 0.5
        asynchronous: true
        cache: false
        smooth: true
        width: Math.max(root.width,root.height*(Math.max(1,implicitWidth)/Math.max(1,implicitHeight)))
        height: Math.max(root.height,root.width/(Math.max(1,implicitWidth)/Math.max(1,implicitHeight)))
        x: (root.width-width)/2
        y: (root.height-height)*position
        visible: !root.usingFirst
        onStatusChanged: root.loaded(second)
    }
    Timer {id: rotation;repeat:false;onTriggered:root.nextPhoto()}
}
