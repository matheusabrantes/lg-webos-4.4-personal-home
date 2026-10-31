import QtQuick 2.4
import WebOSServices 1.0
import "InputLogic.js" as Logic

Item {
    id:root
    property string appId:""
    property string currentAppId:""
    property var fallbackInputs:[]
    property var lockOut:[]
    property var inputData:null
    property var storageData:null
    property bool inputsReceived:false
    property bool storageReceived:false
    property string pendingUsb:""
    property string pendingAuthorization:""
    property string errorMessage:""
    readonly property bool loading:!inputsReceived||!storageReceived
    readonly property var rows:Logic.rows(inputData,storageData,fallbackInputs,currentAppId)
    signal launchRequested(var entry)
    signal selectionFailed(string message)

    function start() {
        inputService.callService({subscribe:true});
        storageService.callService({deviceType:["usb"],subscribe:true});
        loadTimeout.restart();
    }
    function cancelSelection() {pendingUsb="";pendingAuthorization="";validationTimeout.stop();}
    function choose(key,authorized) {
        cancelSelection();
        var entry=Logic.find(rows,key);
        if(!entry){selectionFailed("Esta entrada não está mais disponível.");return;}
        if(!lockOut||typeof lockOut.indexOf!=="function"){selectionFailed("Não foi possível conferir os bloqueios da TV.");return;}
        if(!authorized&&(lockOut.indexOf("inputpicker")>=0||lockOut.indexOf(entry.appId)>=0)){
            pendingAuthorization=key;
            pinService.callService({sourceId:appId,promptType:"parental",title:qsTr("Passcode"),message:""});
            return;
        }
        if(entry.kind!=="usb"){launchRequested(entry);return;}
        pendingUsb=key;validationTimeout.restart();
        validationService.callService({deviceType:["usb"],subscribe:false});
    }
    function receivePin(payload) {
        var data=null;try{data=JSON.parse(payload);}catch(error){}
        if(data&&data.returnValue&&data.matched&&pendingAuthorization){var key=pendingAuthorization;pendingAuthorization="";choose(key,true);}
    }
    function receive(kind,payload) {
        var data=null;try{data=JSON.parse(payload);}catch(error){}
        if(kind==="inputs"){inputsReceived=true;if(data&&data.returnValue)inputData=data;else errorMessage="Não foi possível atualizar as entradas.";}
        else if(kind==="storage"){storageReceived=true;if(data&&data.returnValue)storageData=data;else errorMessage="Não foi possível atualizar o USB.";}
        else if(pendingUsb){
            var key=pendingUsb;cancelSelection();
            if(!data||!data.returnValue){selectionFailed("Não foi possível conferir o pendrive. Tente novamente.");return;}
            storageData=data;
            var entry=Logic.find(Logic.rows(inputData,data,fallbackInputs,currentAppId),key);
            if(entry)launchRequested(entry);else selectionFailed("O pendrive foi removido ou não está disponível.");
        }
        if(!loading)loadTimeout.stop();
    }
    Service {id:inputService;objectName:"inputsEimService";appId:root.appId;service:"com.webos.service.eim";method:"getAllInputStatus";onResponse:root.receive("inputs",payload)}
    Service {id:storageService;objectName:"inputsStorageService";appId:root.appId;service:"com.webos.service.attachedstoragemanager";method:"listDevices";onResponse:root.receive("storage",payload)}
    Service {id:validationService;objectName:"inputsValidationService";appId:root.appId;service:"com.webos.service.attachedstoragemanager";method:"listDevices";onResponse:root.receive("validate",payload)}
    Service {id:pinService;objectName:"inputsPinService";appId:root.appId;service:"com.webos.notification";method:"createPincodePrompt";onResponse:root.receivePin(payload)}
    Timer {id:loadTimeout;interval:6000;onTriggered:{root.inputsReceived=true;root.storageReceived=true;root.errorMessage="Não foi possível atualizar todos os dispositivos.";}}
    Timer {id:validationTimeout;interval:3500;onTriggered:{root.pendingUsb="";root.selectionFailed("O pendrive não respondeu. Tente novamente.");}}
}
