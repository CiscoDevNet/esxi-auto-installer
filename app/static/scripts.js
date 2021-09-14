function InstallDiskShow(itemclickedon) {
  // alert(itemclickedon);
  if (itemclickedon == "firstdisk") {
    FistDiskTypeControls.style.display = "block";
  } else {
    FistDiskTypeControls.style.display = "none";
  }
  if (itemclickedon == "disk") {
    DiskPathTypeControls.style.display = "block";
    DiskPath.required = true
  } else {
    DiskPathTypeControls.style.display = "none";
    DiskPath.required = false
  }
}
function IPListShow(itemclickedon) {
  // alert(itemclickedon);
  if (itemclickedon == "CSV") {
    CSV.style.display = "block";
  } else {
    CSV.style.display = "none";
  }
  if (itemclickedon == "ManualIP") {
    ManualIP.style.display = "block";
  } else {
    ManualIP.style.display = "none";
  }
}
function AddManualIPRow() {
  ServerCount++
  if (ServerCount<=99) { ServerCountStr = ("0"+ServerCount).slice(-2); }
  var table = document.getElementById('ManualIPTable');
  //var columns = ManualIPTable.rows[0].cells.length;
  var tr = table.insertRow(); //ManualIPTable.rows.length
  var CellCount;
  CellCount = 0;

  //Hostname Prefix
  //var td = document.createElement('td')
  td = tr.insertCell(CellCount);
  td.setAttribute('class','prefix');
  td.setAttribute('id','HOSTPREFIXStr' + ServerCount);
  td.innerHTML = document.getElementById('HOSTPREFIX').value;
  CellCount++
  //Unique hostname
  td = tr.insertCell(CellCount);
  td.setAttribute('class','hostname');
  var newelement = document.createElement('input');
  newelement.setAttribute('type','text');
  newelement.setAttribute('name','HOSTNAME' + ServerCount);
  newelement.setAttribute('required', '');
  if (ServerCount > 1) {
    prevValue = ManualIPTable.rows[ServerCount-1].children[CellCount].childNodes[0].value;
    if (isNaN(prevValue) == false) {
      IntValue = parseInt(prevValue);
      IntValue++
      newValue = ''.padStart(prevValue.length - IntValue.toString().length, '0') + IntValue
      newelement.setAttribute('Value',newValue);
    }
  } else {
    newelement.setAttribute('Value','01');
  }
  //newelement.setAttribute('Value',ServerCountStr);
  td.appendChild(newelement);
  CellCount++
  //Hostname suffix
  td = tr.insertCell(CellCount);
  td.setAttribute('class','suffix');
  td.setAttribute('id','HOSTSUFFIXStr' + ServerCount);
  td.innerHTML = document.getElementById('HOSTSUFFIX').value;
  CellCount++
  //Unique IP Address
  td = tr.insertCell(CellCount);
  td.setAttribute('class','ipaddr');
  var newelement = document.createElement('input');
  newelement.setAttribute('type','text');
  newelement.setAttribute('name','IPADDR' + ServerCount);
  newelement.setAttribute('required', '');
  newelement.setAttribute('placeholder',"192.168.100.10");
  if (ServerCount > 1) {
    prevIP = ManualIPTable.rows[ServerCount-1].children[CellCount].childNodes[0].value.split('.')
    //console.log(prevIP)
    if (parseInt(prevIP[3]) < 254) {
      newelement.setAttribute('Value', ([prevIP[0], prevIP[1], prevIP[2], (parseInt(prevIP[3]) + 1)].join('.')))
    }
  }
  //newelement.setAttribute('Value',ServerCount);
  td.appendChild(newelement);
  CellCount++
  //Unique CIMC IP Address
  td = tr.insertCell(CellCount);
  td.setAttribute('class','ipaddr');
  var newelement = document.createElement('input');
  newelement.setAttribute('type','text');
  newelement.setAttribute('name','CIMCIP' + ServerCount);
  newelement.setAttribute('required', '');
  newelement.setAttribute('placeholder',"192.168.200.10[:port]");
  if (ServerCount > 1) {
    prevCIMCIP = ManualIPTable.rows[ServerCount-1].children[CellCount].childNodes[0].value.split('.')
    //console.log(prevCIMCIP)
    if (parseInt(prevCIMCIP[3]) < 254) {
      newelement.setAttribute('Value', ([prevCIMCIP[0], prevCIMCIP[1], prevCIMCIP[2], (parseInt(prevCIMCIP[3]) + 1)].join('.')))
    }
  }
  //newelement.setAttribute('Value',ServerCount);
  td.appendChild(newelement);
  CellCount++
}

function RemoveManualIPRow() {
  if (ServerCount > 1) {
    document.getElementById('ManualIPTable').deleteRow(ServerCount);
    ServerCount--;
  }
}

function UpdateESXiHostName() {
  var prefix = document.getElementById("HOSTPREFIX").value;
  var suffix = document.getElementById("HOSTSUFFIX").value;
  var table = document.getElementById('ManualIPTable');
  var i;
  for (i = 1; i < document.getElementById('ManualIPTable').rows.length; i++)  {
    document.getElementById('HOSTPREFIXStr' + i).innerText = prefix;
    document.getElementById('HOSTSUFFIXStr' + i).innerText = suffix;
  }
}

function StaticRoutesShow(itemclickedon) {
  // alert(itemclickedon);
  var table = document.getElementById('StaticRouteTable');
  var i;
  if (itemclickedon == "True") {
    StaticRoutes.style.display = "block";
    console.log('Adding required for static routes: ' + table.rows.length)
    for (i = 0; i < table.rows.length; i++)  {
      console.log('StaticSubnet' + i)
      document.getElementById('StaticSubnet' + i).setAttribute('required','');
      document.getElementById('StaticMask' + i).setAttribute('required','');
      document.getElementById('StaticGateway' + i).setAttribute('required','');
    }
  } else {
    StaticRoutes.style.display = "none";
    console.log('Removing required for static routes: ' + table.rows.length)
    for (i = 0; i < table.rows.length; i++)  {
      console.log('StaticSubnet' + i)
      document.getElementById('StaticSubnet' + i).removeAttribute('required','');
      document.getElementById('StaticMask' + i).removeAttribute('required','');
      document.getElementById('StaticGateway' + i).removeAttribute('required','');
    }
    // StaticSubnet0.required = false
    // StaticMask0.required = false
    // StaticGateway0.required = false
  }
}

function AddStaticRoute() {
  var table = document.getElementById('StaticRouteTable');
  var tablelength = table.rows.length
  var tr = table.insertRow();
  // Insert IP Subnet Address
  td = tr.insertCell();
  td.setAttribute('style','Border: none; padding: 0px');
  var newelement = document.createElement('input');
  newelement.setAttribute('type','text');
  newelement.setAttribute('name','StaticSubnet' + tablelength);
  newelement.setAttribute('id','StaticSubnet' + tablelength);
  newelement.setAttribute('required', '');
  td.appendChild(newelement);
  td.innerHTML=(td.innerHTML + '/');
  // Add Classless mask
  td = tr.insertCell();
  td.setAttribute('style','Border: none; padding: 0px');
  var newelement = document.createElement('input');
  newelement.setAttribute('required', '');
  newelement.setAttribute('type','number');
  newelement.setAttribute('name','StaticMask' + tablelength);
  newelement.setAttribute('id','StaticMask' + tablelength);
  newelement.setAttribute('value','24');
  newelement.setAttribute('min','0');
  newelement.setAttribute('max','32');
  newelement.setAttribute('size','4');
  td.appendChild(newelement);
  // Add Gateway
  td = tr.insertCell();
  td.setAttribute('style','Border: none; padding: 10px');
  var newelement = document.createElement('input');
  newelement.setAttribute('type','text');
  newelement.setAttribute('name','StaticGateway' + tablelength);
  newelement.setAttribute('id','StaticGateway' + tablelength);
  newelement.setAttribute('required', '');
  td.appendChild(newelement);
}

function RemoveStaticRoute() {
  var table = document.getElementById('StaticRouteTable');
  var tablelength = table.rows.length
  if (tablelength > 1) {
    document.getElementById('StaticRouteTable').deleteRow(-1);
  }
}
