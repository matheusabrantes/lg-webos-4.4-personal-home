.pragma library
var apps = [
    {action:"livetv", title:"TV ao vivo", icon:"tv.png", size:116},
    {action:"abrantesflix", title:"Abrantesflix", icon:"abrantesflix.png", size:125},
    {action:"netflix", title:"Netflix", icon:"netflix.png", size:133},
    {action:"youtube", title:"YouTube", icon:"youtube.png", size:140},
    {action:"amazon", title:"Prime Video", icon:"prime-video.png", size:196},
    {action:"appletv", title:"Apple TV", icon:"apple-tv.png", size:166}
];
var photos = [
    {file:"tv-02.jpg", position:0.5},
    {file:"tv-03.jpg", position:0.5},
    {file:"tv-04.jpg", position:0.5},
    {file:"tv-05.jpg", position:0.5},
    {file:"tv-06.jpg", position:0.5},
    {file:"tv-07.jpg", position:0.5},
    {file:"tv-08.jpg", position:0.5},
    {file:"tv-09.jpg", position:0.5},
    {file:"tv-10.jpg", position:0.5},
    {file:"tv-11.jpg", position:0.5},
    {file:"tv-12.jpg", position:0.5},
    {file:"tv-13.jpg", position:0.5},
    {file:"tv-14.jpg", position:0.5},
    {file:"tv-15.jpg", position:0.5},
    {file:"tv-16.jpg", position:0.5},
    {file:"tv-17.jpg", position:0.5},
    {file:"tv-18.jpg", position:0.5},
    {file:"tv-19.jpg", position:0.5},
    {file:"tv-20.jpg", position:0.5},
    {file:"tv-21.jpg", position:0.5},
    {file:"tv-22.jpg", position:0.5}
];
var actions = ["livetv","abrantesflix","netflix","youtube","amazon","appletv","inputs","wifi","store","settings","original","back"];
function allowed(action) { return actions.indexOf(action) !== -1; }
function dateParts(milliseconds) {
    var date = new Date(milliseconds - 10800000);
    var days = ["Dom","Seg","Ter","Qua","Qui","Sex","Sáb"];
    var months = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
    return {time:("0"+date.getUTCHours()).slice(-2)+":"+("0"+date.getUTCMinutes()).slice(-2),
            date:days[date.getUTCDay()]+" "+date.getUTCDate()+" "+months[date.getUTCMonth()]};
}
function networkLabel(value) { return typeof value === "string" && value.length ? value : "Wi-Fi"; }
function move(index, direction, centers) {
    if (index < 0 || index > 10) return 0;
    if (direction === "next") return (index + 1) % 11;
    if (direction === "previous") return (index + 10) % 11;
    if (direction === "left" || direction === "right") {
        var step = direction === "left" ? -1 : 1;
        if (index < 6) return Math.max(0,Math.min(5,index+step));
        if (index < 10) return Math.max(6,Math.min(9,index+step));
        return index;
    }
    if (direction === "down" && index < 6) return 10;
    if (direction === "up" && index === 10) return 5;
    var first = direction === "up" && index < 6 ? 6 : direction === "down" && index < 10 ? 0 : -1;
    if (first < 0) return index;
    var last = first === 6 ? 9 : 5, best=first, distance=Infinity;
    for (var n=first;n<=last;n++) {
        var delta=Math.abs(centers[n]-centers[index]);
        if (delta < distance) {distance=delta;best=n;}
    }
    return best;
}
