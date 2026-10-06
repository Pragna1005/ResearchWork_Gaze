// let fullAnnotationLog = [];
// let mouseLog = [];
// window.fullAnnotationLog = fullAnnotationLog;
// window.mouseLog = mouseLog;

// // Mouse tracking (move) - sample ~120Hz
// let lastMouseLogTime = 0;
// document.addEventListener("mousemove", (e) => {
//   const now = Date.now();
//   if (now - lastMouseLogTime > 8) {
//     mouseLog.push({
//       type: "move",
//       x: e.clientX + window.scrollX,
//       y: e.clientY + window.scrollY,
//       timestamp: getFormattedTimestamp()
//     });
//     lastMouseLogTime = now;
//   }
// });

// // Capture base timestamp once
// const baseDate = new Date();
// const basePerf = performance.now();

// function getFormattedTimestamp() {
//   const nowPerf = performance.now();
//   const elapsed = nowPerf - basePerf;

//   const now = new Date(baseDate.getTime() + elapsed);
  
//   const pad = (n, width = 2) => n.toString().padStart(width, '0');
//   const date = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
//   const time = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  
//   const msPart = now.getMilliseconds(); // Milliseconds
//   const usDecimal = Math.floor((elapsed % 1) * 1000); // Microsecond fraction

//   const microsecondTotal = msPart * 1000 + usDecimal;

//   return `${date} ${time}.${microsecondTotal}`;
// }


// // Mouse clicks
// document.addEventListener("click", (e) => {
//   mouseLog.push({
//     type: "click",
//    x: e.clientX + window.scrollX,
//       y: e.clientY + window.scrollY,
//       timestamp: getFormattedTimestamp()
//   });
// });

// // Scroll
// window.addEventListener("scroll", () => {
//   mouseLog.push({
//     type: "scroll",
//     x: 0,
//     y: window.scrollY,
//     timestamp: getFormattedTimestamp()
//   });
// });

// // Segment content and annotate
// let blockId = 0;
// document.querySelectorAll("p, h1, h2, h3, img, table").forEach((el) => {
//   const rect = el.getBoundingClientRect();
//   el.setAttribute("data-block-id", blockId);
//   el.classList.add("annotatable-block");

//   const label = document.createElement("div");
//   label.className = "block-label";
//   label.innerHTML = `
//     <button data-help="0" data-block-id="${blockId}">0</button>
//     <button data-help="1" data-block-id="${blockId}">1</button>
//     <button data-help="2" data-block-id="${blockId}">2</button>
//     <button data-help="3" data-block-id="${blockId}">3</button>
//   `;
//   label.style.top = `${rect.top + window.scrollY-20}px`;
// label.style.left = `${rect.left + window.scrollX + rect.width / 2}px`;
// label.style.transform = "translateX(-50%)";

//   document.body.appendChild(label);

//   label.querySelectorAll("button").forEach((btn) => {
//     btn.onclick = () => {
//       const val = btn.getAttribute("data-help");
//       const btnBlockId = btn.getAttribute("data-block-id");
//       const time = getFormattedTimestamp();
//       const content = (el.innerText || el.alt || el.src || "").trim().slice(0, 500);

//       fullAnnotationLog.push({
//         blockId: btnBlockId,
//         timestamp: time,
//         helpfulness: val,
//         content,
//         tag: el.tagName,
//         x: rect.left + window.scrollX,
//         y: rect.top + window.scrollY,
//         width: rect.width,
//         height: rect.height
//       });

//       addToSidebar(content, val);
//     };
//   });

//   blockId++;
// });

// // Inject sidebar
// fetch(chrome.runtime.getURL("sidebar.html"))
//   .then(res => res.text())
//   .then(html => {
//     const div = document.createElement("div");
//     div.innerHTML = html;
//     document.body.appendChild(div);
//     const script = document.createElement("script");
//     script.src = chrome.runtime.getURL("sidebar.js");
//     document.body.appendChild(script);
//   });

// function addToSidebar(content, val) {
//   const item = document.createElement("li");
//   item.textContent = `(${val}) ${content.slice(0, 60)}...`;
//   document.getElementById("snippet-list").appendChild(item);
// }

// // Handle messages from sidebar.js
// window.addEventListener("message", (event) => {
//   if (event.source !== window) return;

//   if (event.data.type === "REQUEST_ANNOTATIONS") {
//     window.postMessage({ type: "ANNOTATIONS_DATA", data: fullAnnotationLog }, "*");
//   }

//   if (event.data.type === "REQUEST_MOUSE_LOGS") {
//     window.postMessage({ type: "MOUSE_DATA", data: mouseLog }, "*");
//   }
// });



// -------------------------------------------------------------------------------------------


let fullAnnotationLog = [];
let mouseLog = [];
window.fullAnnotationLog = fullAnnotationLog;
window.mouseLog = mouseLog;

// Base sync timestamp (to align with Python)
const baseDate = new Date();
const basePerf = performance.now();

const SCREEN_OFFSET_X = window.screenX;
const SCREEN_OFFSET_Y = window.screenY + (window.outerHeight - window.innerHeight)

function getFormattedTimestamp(){
  const epochMicro = (performance.timeOrigin + performance.now()) * 1000;
  const date = new Date(Math.floor(epochMicro / 1000));
  
  const pad = (n, width = 2) => n.toString().padStart(width, '0');
  const dateStr = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const timeStr = `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  
  const microsecond = Math.floor(epochMicro % 1000000);
  return `${dateStr} ${timeStr}.${microsecond.toString().padStart(6, '0')}`;
}


// Mouse move tracking (~120Hz)
let lastMouseLogTime = 0;
document.addEventListener("mousemove", (e) => {
  const now = Date.now();
  if (now - lastMouseLogTime > 8) {
    mouseLog.push({
      type: "move",
      x: e.clientX + window.scrollX,
      y: e.clientY + window.scrollY,
      timestamp: getFormattedTimestamp()
    });
    lastMouseLogTime = now;
  }
});

// Mouse clicks
document.addEventListener("click", (e) => {
  mouseLog.push({
    type: "click",
    x: e.clientX + window.scrollX,
    y: e.clientY + window.scrollY,
    timestamp: getFormattedTimestamp()
  });
});

// Scroll events
window.addEventListener("scroll", () => {
  mouseLog.push({
    type: "scroll",
    x: 0,
    y: window.scrollY,
    timestamp: getFormattedTimestamp()
  });
});

// =====================
// Segment content blocks
// =====================

let blockId = 0;
const seenElements = new Set();

document.querySelectorAll("p, h1, h2, h3, img, table").forEach((el) => {
  const rect = el.getBoundingClientRect();
  
  // Skip hidden or zero-size
  if (rect.width === 0 || rect.height === 0 || el.offsetParent === null) return;

  // Avoid nested annotation blocks
  let isNested = false;
  let parent = el.parentElement;
  while (parent) {
    if (seenElements.has(parent)) {
      isNested = true;
      break;
    }
    parent = parent.parentElement;
  }
  if (isNested) return;

  seenElements.add(el);

  // Refine paragraph bounds using getClientRects
  let finalRect = rect;
  if (el.tagName.toLowerCase() === "p") {
    const clientRects = Array.from(el.getClientRects()).filter(r => r.width > 10 && r.height > 10);

    // Remove any line that overlaps with floating image/table
    const blocksToAvoid = document.querySelectorAll("img, table");
      const filteredRects = clientRects.filter(lineRect => {
      const lineBox = {
        left: lineRect.left + window.scrollX,
        top: lineRect.top + window.scrollY,
        right: lineRect.right + window.scrollX,
        bottom: lineRect.bottom + window.scrollY
      };

      // Check if it overlaps with any image or table
      const overlaps = Array.from(blocksToAvoid).some(block => {
        const br = block.getBoundingClientRect();
        const blockBox = {
          left: br.left + window.scrollX,
          top: br.top + window.scrollY,
          right: br.right + window.scrollX,
          bottom: br.bottom + window.scrollY
        };

        return !(
          lineBox.right < blockBox.left ||
          lineBox.left > blockBox.right ||
          lineBox.bottom < blockBox.top ||
          lineBox.top > blockBox.bottom
        );
      });

      // Only keep if it does NOT overlap
      return !overlaps;
    });


    if (filteredRects.length > 0) {
      const top = filteredRects[0].top;
      const bottom = filteredRects[filteredRects.length - 1].bottom;
      const left = Math.min(...filteredRects.map(r => r.left));
      const right = Math.max(...filteredRects.map(r => r.right));

      finalRect = {
        top: top,
        left: left,
        width: right - left,
        height: bottom - top
      };
      
      // const debugBox = document.createElement("div");
      // debugBox.style.position = "absolute";
      // debugBox.style.top = `${finalRect.top + window.scrollY}px`;
      // debugBox.style.left = `${finalRect.left + window.scrollX}px`;
      // debugBox.style.width = `${finalRect.width}px`;
      // debugBox.style.height = `${finalRect.height}px`;
      // debugBox.style.border = "2px dashed red";
      // debugBox.style.zIndex = "9998";
      // document.body.appendChild(debugBox);


    }
  }

   // page coords
  const pageX = finalRect.left + window.scrollX;
  const pageY = finalRect.top  + window.scrollY;

  // screen coords
  const screenX = pageX + SCREEN_OFFSET_X;
  const screenY = pageY + SCREEN_OFFSET_Y;

  el.setAttribute("data-block-id", blockId);
  el.classList.add("annotatable-block");

  // Inject label buttons
  const label = document.createElement("div");
  label.className = "block-label";
  label.innerHTML = `
    <button data-help="0" data-block-id="${blockId}">0</button>
    <button data-help="1" data-block-id="${blockId}">1</button>
    <button data-help="2" data-block-id="${blockId}">2</button>
    <button data-help="3" data-block-id="${blockId}">3</button>
  `;
  label.style.top = `${rect.top + window.scrollY+80}px`;
  label.style.left = `${rect.left + window.scrollX + rect.width / 2}px`;
  label.style.transform = "translateX(-50%)";

  document.body.appendChild(label);

  label.querySelectorAll("button").forEach((btn) => {
    btn.onclick = () => {
      const val = btn.getAttribute("data-help");
      const btnBlockId = btn.getAttribute("data-block-id");
      const time = getFormattedTimestamp();
      const content = (el.innerText || el.alt || el.src || "").trim().slice(0, 500);

      fullAnnotationLog.push({
        blockId: btnBlockId,
        timestamp: time,
        helpfulness: val,
        content,
        tag: el.tagName,
        x: finalRect.left + window.scrollX,
        y: finalRect.top + window.scrollY,
        width: finalRect.width,
        height: finalRect.height,

        // x: screenX,
        // y: screenY,
        // width: finalRect.width,
        // height: finalRect.height,

        x_screen:    screenX,
        y_screen:    screenY,
        

      });

      addToSidebar(content, val);
    };
  });

  blockId++;
});

// Inject sidebar
fetch(chrome.runtime.getURL("sidebar.html"))
  .then(res => res.text())
  .then(html => {
    const div = document.createElement("div");
    div.innerHTML = html;
    document.body.appendChild(div);

    const script = document.createElement("script");
    script.src = chrome.runtime.getURL("sidebar.js");
    document.body.appendChild(script);
  });

// Sidebar log
function addToSidebar(content, val) {
  const item = document.createElement("li");
  item.textContent = `(${val}) ${content.slice(0, 60)}...`;
  document.getElementById("snippet-list").appendChild(item);
}

// Message handling from sidebar.js
window.addEventListener("message", (event) => {
  if (event.source !== window) return;

  if (event.data.type === "REQUEST_ANNOTATIONS") {
    window.postMessage({ type: "ANNOTATIONS_DATA", data: fullAnnotationLog }, "*");
  }

  if (event.data.type === "REQUEST_MOUSE_LOGS") {
    window.postMessage({ type: "MOUSE_DATA", data: mouseLog }, "*");
  }
});


// ------------------------------------------------------------------------------------------------------

