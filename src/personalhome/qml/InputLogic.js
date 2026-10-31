.pragma library

function rows(eim,storage,fallback,currentApp) {
    var result=[{key:"tv",label:"TV ao vivo",kind:"tv",appId:"com.webos.app.livetv",params:{},current:currentApp==="com.webos.app.livetv",enabled:true,disconnected:false,status:""}], seen={};
    var devices=eim&&eim.returnValue&&Array.isArray(eim.devices)?eim.devices:fallback||[];
    devices=devices.filter(function(d){return d&&typeof d.id==="string"&&typeof d.appId==="string";});
    devices.slice().sort(function(a,b){return (a.id.indexOf("HDMI_")===0?0:1)-(b.id.indexOf("HDMI_")===0?0:1)||(Number(a.port)||0)-(Number(b.port)||0);}).forEach(function(d){
        var hdmi=/^HDMI_([1-9])$/.exec(d.id||""), allowed=hdmi?d.appId==="com.webos.app.hdmi"+hdmi[1]:d.id==="AV_1"&&d.appId==="com.webos.app.externalinput.av1"||d.id==="COMP_1"&&d.appId==="com.webos.app.externalinput.component";
        if(!allowed||d.chosen===false||seen[d.id])return;
        seen[d.id]=true;
        var params={},disconnected=!!hdmi&&d.activate===false;
        if(hdmi&&typeof d.uniqueId==="number"&&isFinite(d.uniqueId)&&d.uniqueId>0&&Math.floor(d.uniqueId)===d.uniqueId)params={id:"uniqueId",value:String(d.uniqueId)};
        result.push({key:d.id,label:String(d.label||d.id).slice(0,120),kind:hdmi?"hdmi":"av",appId:d.appId,params:params,current:currentApp===d.appId,enabled:true,disconnected:disconnected,status:disconnected?"Sem sinal":""});
    });
    if(storage&&storage.returnValue&&Array.isArray(storage.devices))storage.devices.forEach(function(d){
        if(!d||d.deviceType!=="usb"||["NORMAL","SUSPEND"].indexOf(d.deviceStatus)<0||typeof d.deviceId!=="string"||!d.deviceId||d.deviceId.length>256||seen[d.deviceId])return;
        seen[d.deviceId]=true;
        result.push({key:"usb:"+d.deviceId,label:String(d.deviceName||"Pendrive USB").slice(0,120),kind:"usb",appId:"com.webos.app.photovideo",params:{requestDevice:d.deviceId},current:false,enabled:true,disconnected:false,status:"USB"});
    });
    return result;
}

function find(rows,key) {
    for(var i=0;i<rows.length;i++)if(rows[i].key===key)return rows[i];
    return null;
}
