import QtQuick 2.4

Canvas {
    id: icon
    property color ink: "white"
    implicitWidth: 28
    implicitHeight: 28
    antialiasing: true
    onInkChanged: requestPaint()
    onPaint: {
        var ctx=getContext("2d");
        ctx.reset();
        ctx.strokeStyle=ink; ctx.lineWidth=2;
        ctx.lineCap="round"; ctx.lineJoin="round";
        ctx.beginPath();
        ctx.moveTo(3,8);ctx.lineTo(7,8);ctx.moveTo(15,8);ctx.lineTo(25,8);
        ctx.moveTo(3,20);ctx.lineTo(13,20);ctx.moveTo(21,20);ctx.lineTo(25,20);
        ctx.moveTo(15,8);ctx.arc(11,8,4,0,Math.PI*2);
        ctx.moveTo(21,20);ctx.arc(17,20,4,0,Math.PI*2);
        ctx.stroke();
    }
}
