// mathjax-sidecar.mjs
import readline from "node:readline";

// node_modules/@mathjax/src/mjs/components/version.js
var VERSION = "4.1.3";

// node_modules/@mathjax/src/mjs/util/PrioritizedList.js
var PrioritizedList = class _PrioritizedList {
  constructor() {
    this.items = [];
    this.items = [];
  }
  [Symbol.iterator]() {
    let i = 0;
    const items = this.items;
    return {
      next() {
        return { value: items[i++], done: i > items.length };
      }
    };
  }
  add(item, priority = _PrioritizedList.DEFAULTPRIORITY) {
    let i = this.items.length;
    do {
      i--;
    } while (i >= 0 && priority < this.items[i].priority);
    this.items.splice(i + 1, 0, { item, priority });
    return item;
  }
  remove(item) {
    let i = this.items.length;
    do {
      i--;
    } while (i >= 0 && this.items[i].item !== item);
    if (i >= 0) {
      this.items.splice(i, 1);
    }
    return this;
  }
};
PrioritizedList.DEFAULTPRIORITY = 5;

// node_modules/@mathjax/src/mjs/core/HandlerList.js
var HandlerList = class extends PrioritizedList {
  register(handler) {
    return this.add(handler, handler.priority);
  }
  unregister(handler) {
    this.remove(handler);
  }
  handlesDocument(document2) {
    for (const item of this) {
      const handler = item.item;
      if (handler.handlesDocument(document2)) {
        return handler;
      }
    }
    throw new Error(`Can't find handler for document`);
  }
  document(document2, options2 = null) {
    return this.handlesDocument(document2).create(document2, options2);
  }
};

// node_modules/@mathjax/src/mjs/util/Retries.js
function handleRetriesFor(code) {
  return new Promise(function run(ok, fail) {
    const handleRetry = (err) => {
      var _a;
      if (err.retry instanceof Promise) {
        err.retry.then(() => run(ok, fail)).catch((e) => fail(e));
      } else if ((_a = err.restart) === null || _a === void 0 ? void 0 : _a.isCallback) {
        MathJax.Callback.After(() => run(ok, fail), err.restart);
      } else {
        fail(err);
      }
    };
    try {
      const result = code();
      if (result instanceof Promise) {
        result.then((value) => ok(value)).catch((err) => handleRetry(err));
      } else {
        ok(result);
      }
    } catch (err) {
      handleRetry(err);
    }
  });
}
function retryAfter(promise) {
  const err = new Error("MathJax retry -- an asynchronous action is required; try using one of the promise-based functions and await its resolution.");
  err.retry = promise;
  throw err;
}

// node_modules/@mathjax/src/mjs/util/context.js
var hasWindow = typeof window !== "undefined";
var isCJS = typeof exports !== "undefined";
var context = {
  window: hasWindow ? window : null,
  document: hasWindow ? window.document : null,
  os: (() => {
    if (hasWindow && window.navigator) {
      const app = window.navigator.appVersion;
      const osNames = [
        ["Win", "Windows"],
        ["Mac", "MacOS"],
        ["X11", "Unix"],
        ["Linux", "Unix"]
      ];
      for (const [key, os] of osNames) {
        if (app.includes(key)) {
          return os;
        }
      }
      if (window.navigator.userAgent.includes("Android")) {
        return "Unix";
      }
    } else if (typeof process !== "undefined") {
      return {
        linux: "Unix",
        android: "Unix",
        aix: "Unix",
        freebsd: "Unix",
        netbsd: "Unix",
        openbsd: "Unix",
        sunos: "Unix",
        darwin: "MacOS",
        win32: "Windows",
        cygwin: "Windows"
      }[process.platform] || process.platform;
    }
    return "unknown";
  })(),
  path: (file) => file
};
if (context.os === "Windows") {
  context.path = (file) => file.match(/^[/\\]?[a-zA-Z]:[/\\]/) ? (isCJS ? "" : "file://") + file.replace(/\\/g, "/").replace(/^\//, "") : file.replace(/^\//, "file:///");
}

// node_modules/@mathjax/src/mjs/mathjax.js
var mathjax = {
  version: VERSION,
  context,
  handlers: new HandlerList(),
  document: function(document2, options2) {
    return mathjax.handlers.document(document2, options2);
  },
  handleRetriesFor,
  retryAfter,
  asyncLoad: null,
  asyncIsSynchronous: false
};

// node_modules/@mathjax/src/mjs/util/Options.js
var OBJECT = {}.constructor;
function isObject(obj) {
  return typeof obj === "object" && obj !== null && (obj.constructor === OBJECT || obj.constructor === Expandable);
}
var APPEND = "[+]";
var REMOVE = "[-]";
var OPTIONS = {
  invalidOption: "warn",
  optionError: (message, _key) => {
    if (OPTIONS.invalidOption === "fatal") {
      throw new Error(message);
    }
    console.warn("MathJax: " + message);
  }
};
var Expandable = class {
};
function expandable(def) {
  return Object.assign(Object.create(Expandable.prototype), def);
}
function makeArray(x) {
  return Array.isArray(x) ? x : [x];
}
function keys(def) {
  if (!def) {
    return [];
  }
  return Object.keys(def).concat(Object.getOwnPropertySymbols(def));
}
function copy(def) {
  const props = {};
  for (const key of keys(def)) {
    const prop = Object.getOwnPropertyDescriptor(def, key);
    const value = prop.value;
    if (Array.isArray(value)) {
      prop.value = insert([], value, false);
    } else if (isObject(value)) {
      prop.value = copy(value);
    }
    if (prop.enumerable) {
      props[key] = prop;
    }
  }
  return Object.defineProperties(def.constructor === Expandable ? expandable({}) : {}, props);
}
function insert(dst, src, warn = true) {
  for (let key of keys(src)) {
    if (warn && dst[key] === void 0 && dst.constructor !== Expandable) {
      if (typeof key === "symbol") {
        key = key.toString();
      }
      OPTIONS.optionError(`Invalid option "${key}" (no default value).`, key);
      continue;
    }
    const sval = src[key];
    let dval = dst[key];
    if (isObject(sval) && dval !== null && (typeof dval === "object" || typeof dval === "function")) {
      const ids = keys(sval);
      if (Array.isArray(dval) && (ids.length === 1 && (ids[0] === APPEND || ids[0] === REMOVE) && Array.isArray(sval[ids[0]]) || ids.length === 2 && ids.sort().join(",") === APPEND + "," + REMOVE && Array.isArray(sval[APPEND]) && Array.isArray(sval[REMOVE]))) {
        if (sval[REMOVE]) {
          dval = dst[key] = dval.filter((x) => sval[REMOVE].indexOf(x) < 0);
        }
        if (sval[APPEND]) {
          dst[key] = [...dval, ...sval[APPEND]];
        }
      } else {
        insert(dval, sval, warn);
      }
    } else if (Array.isArray(sval)) {
      dst[key] = [];
      insert(dst[key], sval, false);
    } else if (isObject(sval)) {
      dst[key] = copy(sval);
    } else {
      dst[key] = sval;
    }
  }
  return dst;
}
function defaultOptions(options2, ...defs) {
  defs.forEach((def) => insert(options2, def, false));
  return options2;
}
function userOptions(options2, ...defs) {
  defs.forEach((def) => insert(options2, def, true));
  return options2;
}
function separateOptions(options2, ...objects) {
  const results = [];
  for (const object of objects) {
    const exists = {}, missing = {};
    for (const key of Object.keys(options2 || {})) {
      (object[key] === void 0 ? missing : exists)[key] = options2[key];
    }
    results.push(exists);
    options2 = missing;
  }
  results.unshift(options2);
  return results;
}
function lookup(name, lookup2, def = null) {
  return Object.hasOwn(lookup2, name) ? lookup2[name] : def;
}

// node_modules/@mathjax/src/mjs/util/FunctionList.js
var FunctionList = class extends PrioritizedList {
  constructor(list = null) {
    super();
    if (list) {
      this.addList(list);
    }
  }
  addList(list) {
    for (const item of list) {
      if (Array.isArray(item)) {
        this.add(item[0], item[1]);
      } else {
        this.add(item);
      }
    }
  }
  execute(...data) {
    for (const item of this) {
      const result = item.item(...data);
      if (result === false) {
        return false;
      }
    }
    return true;
  }
  asyncExecute(...data) {
    let i = -1;
    const items = this.items;
    return new Promise((ok, fail) => {
      (function execute() {
        while (++i < items.length) {
          const result = items[i].item(...data);
          if (result instanceof Promise) {
            result.then(execute).catch((err) => fail(err));
            return;
          }
          if (result === false) {
            ok(false);
            return;
          }
        }
        ok(true);
      })();
    });
  }
};

// node_modules/@mathjax/src/mjs/core/InputJax.js
var AbstractInputJax = class {
  constructor(options2 = {}) {
    this.adaptor = null;
    this.mmlFactory = null;
    const CLASS = this.constructor;
    this.options = userOptions(defaultOptions({}, CLASS.OPTIONS), options2);
    this.preFilters = new FunctionList(this.options.preFilters);
    this.postFilters = new FunctionList(this.options.postFilters);
  }
  get name() {
    return this.constructor.NAME;
  }
  setAdaptor(adaptor2) {
    this.adaptor = adaptor2;
  }
  setMmlFactory(mmlFactory) {
    this.mmlFactory = mmlFactory;
  }
  initialize() {
  }
  reset(..._args) {
  }
  get processStrings() {
    return true;
  }
  findMath(_node, _options) {
    return [];
  }
  executeFilters(filters, math, document2, data) {
    const args = { math, document: document2, data };
    filters.execute(args);
    return args.data;
  }
};
AbstractInputJax.NAME = "generic";
AbstractInputJax.OPTIONS = {
  preFilters: [],
  postFilters: []
};

// node_modules/@mathjax/src/mjs/core/FindMath.js
var AbstractFindMath = class {
  constructor(options2) {
    const CLASS = this.constructor;
    this.options = userOptions(defaultOptions({}, CLASS.OPTIONS), options2);
  }
};
AbstractFindMath.OPTIONS = {};

// node_modules/@mathjax/src/mjs/util/string.js
function sortLength(a, b) {
  return a.length !== b.length ? b.length - a.length : a === b ? 0 : a < b ? -1 : 1;
}
function quotePattern(text) {
  return text.replace(/([\^$(){}.+*?\-|[\]:\\])/g, "\\$1");
}
function unicodeChars(text) {
  return Array.from(text).map((c) => c.codePointAt(0));
}
function unicodeString(data) {
  return String.fromCodePoint(...data);
}
function split(x) {
  return x.trim().split(/\s+/);
}
function replaceUnicode(text) {
  return text.replace(/\\U(?:([0-9A-Fa-f]{4})|\{\s*([0-9A-Fa-f]{1,6})\s*\})|\\./g, (m, h1, h2) => m === "\\\\" ? "\\" : String.fromCodePoint(parseInt(h1 || h2, 16)));
}
function toEntity(c) {
  return `&#x${c.codePointAt(0).toString(16).toUpperCase()};`;
}

// node_modules/@mathjax/src/mjs/core/MathItem.js
function protoItem(open, math, close, n, start, end, display = null) {
  const item = {
    open,
    math,
    close,
    n,
    start: { n: start },
    end: { n: end },
    display
  };
  return item;
}
var AbstractMathItem = class {
  get isEscaped() {
    return this.display === null;
  }
  constructor(math, jax, display = true, start = { i: 0, n: 0, delim: "" }, end = { i: 0, n: 0, delim: "" }) {
    this.root = null;
    this.typesetRoot = null;
    this.metrics = {};
    this.inputData = {};
    this.outputData = {};
    this._state = STATE.UNPROCESSED;
    this.math = math;
    this.inputJax = jax;
    this.display = display;
    this.start = start;
    this.end = end;
    this.root = null;
    this.typesetRoot = null;
    this.metrics = {};
    this.inputData = {};
    this.outputData = {};
  }
  render(document2) {
    document2.renderActions.renderMath(this, document2);
  }
  rerender(document2, start = STATE.RERENDER) {
    if (this.state() >= start) {
      this.state(start - 1);
    }
    document2.renderActions.renderMath(this, document2, start);
  }
  convert(document2, end = STATE.LAST) {
    document2.renderActions.renderConvert(this, document2, end);
  }
  compile(document2) {
    if (this.state() < STATE.COMPILED) {
      this.root = this.inputJax.compile(this, document2);
      this.state(STATE.COMPILED);
    }
  }
  typeset(document2) {
    if (this.state() < STATE.TYPESET) {
      this.typesetRoot = document2.outputJax[this.isEscaped ? "escaped" : "typeset"](this, document2);
      this.state(STATE.TYPESET);
    }
  }
  updateDocument(_document) {
  }
  removeFromDocument(_restore = false) {
    this.clear();
  }
  setMetrics(em2, ex, cwidth, scale) {
    this.metrics = {
      em: em2,
      ex,
      containerWidth: cwidth,
      scale
    };
  }
  state(state = null, restore = false) {
    if (state != null) {
      if (state < STATE.INSERTED && this._state >= STATE.INSERTED) {
        this.removeFromDocument(restore);
      }
      if (state < STATE.TYPESET && this._state >= STATE.TYPESET) {
        this.outputData = {};
      }
      if (state < STATE.COMPILED && this._state >= STATE.COMPILED) {
        this.inputData = {};
      }
      this._state = state;
    }
    return this._state;
  }
  reset(restore = false) {
    this.state(STATE.UNPROCESSED, restore);
  }
  clear() {
  }
};
var STATE = {
  UNPROCESSED: 0,
  FINDMATH: 10,
  COMPILED: 20,
  CONVERT: 100,
  METRICS: 110,
  RERENDER: 125,
  TYPESET: 150,
  INSERTED: 200,
  LAST: 1e4
};
function newState(name, state) {
  if (name in STATE) {
    throw Error("State " + name + " already exists");
  }
  STATE[name] = state;
}

// node_modules/@mathjax/src/mjs/input/tex/FindTeX.js
var FindTeX = class extends AbstractFindMath {
  constructor(options2) {
    super(options2);
    this.getPatterns();
  }
  getPatterns() {
    const options2 = this.options;
    const starts = [];
    const parts = [];
    const subparts = [];
    this.end = {};
    this.env = this.sub = 0;
    let i = 1;
    options2["inlineMath"].forEach((delims) => this.addPattern(starts, delims, false));
    options2["displayMath"].forEach((delims) => this.addPattern(starts, delims, true));
    if (starts.length) {
      parts.push(starts.sort(sortLength).join("|"));
    }
    if (options2["processEnvironments"]) {
      parts.push("\\\\begin\\s*\\{([^}]*)\\}");
      this.env = i;
      i++;
    }
    if (options2["processEscapes"]) {
      subparts.push("\\\\([\\\\$])");
    }
    if (options2["processRefs"]) {
      subparts.push("(\\\\(?:eq)?ref\\s*\\{[^}]*\\})");
    }
    if (subparts.length) {
      parts.push("(" + subparts.join("|") + ")");
      this.sub = i;
    }
    this.start = new RegExp(parts.join("|"), "g");
    this.hasPatterns = parts.length > 0;
  }
  addPattern(starts, delims, display) {
    const [open, close] = delims;
    starts.push(quotePattern(open));
    this.end[open] = [close, display, this.endPattern(close)];
  }
  endPattern(end, endp) {
    return new RegExp((endp || quotePattern(end)) + "|\\\\(?:[a-zA-Z]|.)|[{}]", "g");
  }
  findEnd(text, n, start, end) {
    const [close, display, pattern] = end;
    const i = pattern.lastIndex = start.index + start[0].length;
    let match, braces = 0;
    while (match = pattern.exec(text)) {
      if ((match[1] || match[0]) === close && braces === 0) {
        return protoItem(start[0], text.substring(i, match.index), match[0], n, start.index, match.index + match[0].length, display);
      } else if (match[0] === "{") {
        braces++;
      } else if (match[0] === "}" && braces) {
        braces--;
      }
    }
    return null;
  }
  findMathInString(math, n, text) {
    let start, match;
    this.start.lastIndex = 0;
    while (start = this.start.exec(text)) {
      if (start[this.env] !== void 0 && this.env) {
        const end = "\\\\end\\s*(\\{" + quotePattern(start[this.env]) + "\\})";
        match = this.findEnd(text, n, start, [
          "{" + start[this.env] + "}",
          true,
          this.endPattern(null, end)
        ]);
        if (match) {
          match.math = match.open + match.math + match.close;
          match.open = match.close = "";
        }
      } else if (start[this.sub] !== void 0 && this.sub) {
        const math2 = start[this.sub];
        const end = start.index + start[this.sub].length;
        if (math2.length === 2) {
          match = protoItem("\\", math2.substring(1), "", n, start.index, end);
        } else {
          match = protoItem("", math2, "", n, start.index, end, false);
        }
      } else {
        match = this.findEnd(text, n, start, this.end[start[0]]);
      }
      if (match) {
        math.push(match);
        this.start.lastIndex = match.end.n;
      }
    }
  }
  findMath(strings) {
    const math = [];
    if (this.hasPatterns) {
      for (let i = 0, m = strings.length; i < m; i++) {
        this.findMathInString(math, i, strings[i]);
      }
    }
    return math;
  }
};
FindTeX.OPTIONS = {
  inlineMath: [
    ["\\(", "\\)"]
  ],
  displayMath: [
    ["$$", "$$"],
    ["\\[", "\\]"]
  ],
  processEscapes: true,
  processEnvironments: true,
  processRefs: true
};

// node_modules/@mathjax/src/mjs/core/MmlTree/Attributes.js
var INHERIT = "_inherit_";
var Attributes = class {
  constructor(defaults, global) {
    this.global = global;
    this.defaults = Object.create(global);
    this.inherited = Object.create(this.defaults);
    this.attributes = Object.create(this.inherited);
    Object.assign(this.defaults, defaults);
  }
  set(name, value) {
    this.attributes[name] = value;
  }
  setList(list) {
    Object.assign(this.attributes, list);
  }
  unset(name) {
    delete this.attributes[name];
  }
  get(name) {
    let value = this.attributes[name];
    if (value === INHERIT) {
      value = this.global[name];
    }
    return value;
  }
  getExplicit(name) {
    return this.hasExplicit(name) ? this.attributes[name] : void 0;
  }
  hasExplicit(name) {
    return Object.hasOwn(this.attributes, name);
  }
  hasOneOf(names) {
    for (const name of names) {
      if (this.hasExplicit(name)) {
        return true;
      }
    }
    return false;
  }
  getList(...names) {
    const values = {};
    for (const name of names) {
      values[name] = this.get(name);
    }
    return values;
  }
  setInherited(name, value) {
    this.inherited[name] = value;
  }
  getInherited(name) {
    return this.inherited[name];
  }
  getDefault(name) {
    return this.defaults[name];
  }
  isSet(name) {
    return Object.hasOwn(this.attributes, name) || Object.hasOwn(this.inherited, name);
  }
  hasDefault(name) {
    return name in this.defaults;
  }
  getExplicitNames() {
    return Object.keys(this.attributes);
  }
  getInheritedNames() {
    return Object.keys(this.inherited);
  }
  getDefaultNames() {
    return Object.keys(this.defaults);
  }
  getGlobalNames() {
    return Object.keys(this.global);
  }
  getAllAttributes() {
    return this.attributes;
  }
  getAllInherited() {
    return this.inherited;
  }
  getAllDefaults() {
    return this.defaults;
  }
  getAllGlobals() {
    return this.global;
  }
};

// node_modules/@mathjax/src/mjs/core/Tree/Node.js
var AbstractNode = class {
  constructor(factory, properties = {}, children = []) {
    this.factory = factory;
    this.parent = null;
    this.properties = {};
    this.childNodes = [];
    for (const name of Object.keys(properties)) {
      this.setProperty(name, properties[name]);
    }
    if (children.length) {
      this.setChildren(children);
    }
  }
  get kind() {
    return "unknown";
  }
  setProperty(name, value) {
    this.properties[name] = value;
  }
  getProperty(name) {
    return this.properties[name];
  }
  getPropertyNames() {
    return Object.keys(this.properties);
  }
  getAllProperties() {
    return this.properties;
  }
  removeProperty(...names) {
    for (const name of names) {
      delete this.properties[name];
    }
  }
  isKind(kind) {
    return this.factory.nodeIsKind(this, kind);
  }
  setChildren(children) {
    this.childNodes = [];
    for (const child of children) {
      this.appendChild(child);
    }
  }
  appendChild(child) {
    this.childNodes.push(child);
    child.parent = this;
    return child;
  }
  replaceChild(newChild, oldChild) {
    const i = this.childIndex(oldChild);
    if (i !== null) {
      this.childNodes[i] = newChild;
      newChild.parent = this;
      if (oldChild.parent === this) {
        oldChild.parent = null;
      }
    }
    return newChild;
  }
  removeChild(child) {
    const i = this.childIndex(child);
    if (i !== null) {
      this.childNodes.splice(i, 1);
      child.parent = null;
    }
    return child;
  }
  childIndex(node) {
    const i = this.childNodes.indexOf(node);
    return i === -1 ? null : i;
  }
  copy() {
    const node = this.factory.create(this.kind);
    node.properties = Object.assign({}, this.properties);
    for (const child of this.childNodes || []) {
      if (child) {
        node.appendChild(child.copy());
      }
    }
    return node;
  }
  findNodes(kind) {
    const nodes = [];
    this.walkTree((node) => {
      if (node.isKind(kind)) {
        nodes.push(node);
      }
    });
    return nodes;
  }
  walkTree(func, data) {
    func(this, data);
    for (const child of this.childNodes) {
      if (child) {
        child.walkTree(func, data);
      }
    }
    return data;
  }
  toString() {
    return this.kind + "(" + this.childNodes.join(",") + ")";
  }
};
var AbstractEmptyNode = class extends AbstractNode {
  setChildren(_children) {
  }
  appendChild(child) {
    return child;
  }
  replaceChild(_newChild, oldChild) {
    return oldChild;
  }
  childIndex(_node) {
    return null;
  }
  walkTree(func, data) {
    func(this, data);
    return data;
  }
  toString() {
    return this.kind;
  }
};

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNode.js
var TEXCLASS = {
  ORD: 0,
  OP: 1,
  BIN: 2,
  REL: 3,
  OPEN: 4,
  CLOSE: 5,
  PUNCT: 6,
  INNER: 7,
  NONE: -1
};
var TEXCLASSNAMES = [
  "ORD",
  "OP",
  "BIN",
  "REL",
  "OPEN",
  "CLOSE",
  "PUNCT",
  "INNER"
];
var TEXSPACELENGTH = [
  "",
  "thinmathspace",
  "mediummathspace",
  "thickmathspace"
];
var TEXSPACE = [
  [0, -1, 2, 3, 0, 0, 0, 1],
  [-1, -1, 0, 3, 0, 0, 0, 1],
  [2, 2, 0, 0, 2, 0, 0, 2],
  [3, 3, 0, 0, 3, 0, 0, 3],
  [0, 0, 0, 0, 0, 0, 0, 0],
  [0, -1, 2, 3, 0, 0, 0, 1],
  [1, 1, 0, 1, 1, 1, 1, 1],
  [1, -1, 2, 3, 1, 0, 1, 1]
];
var MATHVARIANTS = /* @__PURE__ */ new Set([
  "normal",
  "bold",
  "italic",
  "bold-italic",
  "double-struck",
  "fraktur",
  "bold-fraktur",
  "script",
  "bold-script",
  "sans-serif",
  "bold-sans-serif",
  "sans-serif-italic",
  "sans-serif-bold-italic",
  "monospace",
  "inital",
  "tailed",
  "looped",
  "stretched"
]);
var indentAttributes = [
  "indentalign",
  "indentalignfirst",
  "indentshift",
  "indentshiftfirst"
];
var AbstractMmlNode = class _AbstractMmlNode extends AbstractNode {
  constructor(factory, attributes = {}, children = []) {
    super(factory);
    this.prevClass = null;
    this.prevLevel = null;
    this.texclass = null;
    if (this.arity < 0) {
      this.childNodes = [factory.create("inferredMrow")];
      this.childNodes[0].parent = this;
    }
    this.setChildren(children);
    this.attributes = new Attributes(factory.getNodeClass(this.kind).defaults, factory.getNodeClass("math").defaults);
    this.attributes.setList(attributes);
  }
  copy(keepIds = false) {
    const node = this.factory.create(this.kind);
    node.properties = Object.assign({}, this.properties);
    if (this.attributes) {
      const attributes = this.attributes.getAllAttributes();
      for (const name of Object.keys(attributes)) {
        if (name !== "id" || keepIds) {
          node.attributes.set(name, attributes[name]);
        }
      }
    }
    if (this.childNodes && this.childNodes.length) {
      let children = this.childNodes;
      if (children.length === 1 && children[0].isInferred) {
        children = children[0].childNodes;
      }
      for (const child of children) {
        if (child) {
          node.appendChild(child.copy());
        } else {
          node.childNodes.push(null);
        }
      }
    }
    return node;
  }
  get texClass() {
    return this.texclass;
  }
  set texClass(texClass) {
    this.texclass = texClass;
  }
  get isToken() {
    return false;
  }
  get isEmbellished() {
    return false;
  }
  get isSpacelike() {
    return false;
  }
  get linebreakContainer() {
    return false;
  }
  get linebreakAlign() {
    return "data-align";
  }
  get isEmpty() {
    for (const child of this.childNodes) {
      if (child && !child.isEmpty)
        return false;
    }
    return true;
  }
  get arity() {
    return Infinity;
  }
  get isInferred() {
    return false;
  }
  get Parent() {
    let parent = this.parent;
    while (parent && parent.notParent) {
      parent = parent.Parent;
    }
    return parent;
  }
  get notParent() {
    return false;
  }
  setChildren(children) {
    if (this.arity < 0) {
      return this.childNodes[0].setChildren(children);
    }
    return super.setChildren(children);
  }
  appendChild(child) {
    if (this.arity < 0) {
      this.childNodes[0].appendChild(child);
      return child;
    }
    if (child.isInferred) {
      if (this.arity === Infinity) {
        child.childNodes.forEach((node) => super.appendChild(node));
        return child;
      }
      const original = child;
      child = this.factory.create("mrow");
      child.setChildren(original.childNodes);
      child.attributes = original.attributes;
      for (const name of original.getPropertyNames()) {
        child.setProperty(name, original.getProperty(name));
      }
    }
    return super.appendChild(child);
  }
  replaceChild(newChild, oldChild) {
    if (this.arity < 0) {
      this.childNodes[0].replaceChild(newChild, oldChild);
      return newChild;
    }
    return super.replaceChild(newChild, oldChild);
  }
  core() {
    return this;
  }
  coreMO() {
    return this;
  }
  coreIndex() {
    return 0;
  }
  childPosition() {
    let child = null;
    let parent = this.parent;
    while (parent && parent.notParent) {
      child = parent;
      parent = parent.parent;
    }
    child = child || this;
    if (parent) {
      let i = 0;
      for (const node of parent.childNodes) {
        if (node === child) {
          return i;
        }
        i++;
      }
    }
    return null;
  }
  setTeXclass(prev) {
    this.getPrevClass(prev);
    return this.texClass != null ? this : prev;
  }
  updateTeXclass(core) {
    if (core) {
      this.prevClass = core.prevClass;
      this.prevLevel = core.prevLevel;
      core.prevClass = core.prevLevel = null;
      this.texClass = core.texClass;
    }
  }
  getPrevClass(prev) {
    if (prev) {
      this.prevClass = prev.texClass;
      this.prevLevel = prev.attributes.get("scriptlevel");
    }
  }
  texSpacing() {
    const prevClass = this.prevClass != null ? this.prevClass : TEXCLASS.NONE;
    const texClass = this.texClass || TEXCLASS.ORD;
    if (prevClass === TEXCLASS.NONE || texClass === TEXCLASS.NONE) {
      return "";
    }
    const space = TEXSPACE[prevClass][texClass];
    if ((this.prevLevel > 0 || this.attributes.get("scriptlevel") > 0) && space >= 0) {
      return "";
    }
    return TEXSPACELENGTH[Math.abs(space)];
  }
  hasSpacingAttributes() {
    return this.isEmbellished && this.coreMO().hasSpacingAttributes();
  }
  setInheritedAttributes(attributes = {}, display = false, level = 0, prime = false) {
    var _a, _b, _c;
    const defaults = this.attributes.getAllDefaults();
    for (const key of Object.keys(attributes)) {
      if (Object.hasOwn(defaults, key) || Object.hasOwn(_AbstractMmlNode.alwaysInherit, key)) {
        const [node, value] = attributes[key];
        if (!((_b = (_a = _AbstractMmlNode.noInherit[node]) === null || _a === void 0 ? void 0 : _a[this.kind]) === null || _b === void 0 ? void 0 : _b[key])) {
          this.attributes.setInherited(key, value);
        }
      }
      if ((_c = _AbstractMmlNode.stopInherit[this.kind]) === null || _c === void 0 ? void 0 : _c[key]) {
        attributes = Object.assign({}, attributes);
        delete attributes[key];
      }
    }
    const displaystyle = this.attributes.getExplicit("displaystyle");
    if (displaystyle === void 0) {
      this.attributes.setInherited("displaystyle", display);
    }
    const scriptlevel = this.attributes.getExplicit("scriptlevel");
    if (scriptlevel === void 0) {
      this.attributes.setInherited("scriptlevel", level);
    }
    if (prime) {
      this.setProperty("texprimestyle", prime);
    }
    const arity = this.arity;
    if (arity >= 0 && arity !== Infinity && (arity === 1 && this.childNodes.length === 0 || arity !== 1 && this.childNodes.length !== arity)) {
      if (arity < this.childNodes.length) {
        this.childNodes = this.childNodes.slice(0, arity);
      } else {
        while (this.childNodes.length < arity) {
          this.appendChild(this.factory.create("mrow"));
        }
      }
    }
    if (this.linebreakContainer && !this.isEmbellished) {
      const align = this.linebreakAlign;
      if (align) {
        const indentalign = this.attributes.get(align) || "left";
        attributes = this.addInheritedAttributes(attributes, {
          indentalign,
          indentshift: "0",
          indentalignfirst: indentalign,
          indentshiftfirst: "0",
          indentalignlast: "indentalign",
          indentshiftlast: "indentshift"
        });
      }
    }
    this.setChildInheritedAttributes(attributes, display, level, prime);
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    for (const child of this.childNodes) {
      child.setInheritedAttributes(attributes, display, level, prime);
    }
  }
  addInheritedAttributes(current, attributes) {
    const updated = Object.assign({}, current);
    for (const name of Object.keys(attributes)) {
      if (name !== "displaystyle" && name !== "scriptlevel" && name !== "style") {
        updated[name] = [this.kind, attributes[name]];
      }
    }
    return updated;
  }
  inheritAttributesFrom(node) {
    const attributes = node.attributes;
    const display = attributes.get("displaystyle");
    const scriptlevel = attributes.get("scriptlevel");
    const defaults = !attributes.isSet("mathsize") ? {} : { mathsize: ["math", attributes.get("mathsize")] };
    const prime = node.getProperty("texprimestyle") || false;
    this.setInheritedAttributes(defaults, display, scriptlevel, prime);
  }
  verifyTree(options2 = null) {
    if (options2 === null) {
      return;
    }
    this.verifyAttributes(options2);
    const arity = this.arity;
    if (options2["checkArity"]) {
      if (arity >= 0 && arity !== Infinity && (arity === 1 && this.childNodes.length === 0 || arity !== 1 && this.childNodes.length !== arity)) {
        this.mError('Wrong number of children for "' + this.kind + '" node', options2, true);
      }
    }
    this.verifyChildren(options2);
  }
  verifyAttributes(options2) {
    if (options2.checkAttributes) {
      const attributes = this.attributes;
      const bad = [];
      for (const name of attributes.getExplicitNames()) {
        if (name.substring(0, 5) !== "data-" && attributes.getDefault(name) === void 0 && !name.match(/^(?:class|style|id|(?:xlink:)?href)$/)) {
          bad.push(name);
        }
      }
      if (bad.length) {
        this.mError("Unknown attributes for " + this.kind + " node: " + bad.join(", "), options2);
      }
    }
    if (options2.checkMathvariants) {
      const variant = this.attributes.getExplicit("mathvariant");
      if (variant && !MATHVARIANTS.has(variant) && !this.getProperty("ignore-variant")) {
        this.mError(`Invalid mathvariant: ${variant}`, options2, true);
      }
    }
  }
  verifyChildren(options2) {
    for (const child of this.childNodes) {
      child.verifyTree(options2);
    }
  }
  mError(message, options2, short = false) {
    if (this.parent && this.parent.isKind("merror")) {
      return null;
    }
    const merror = this.factory.create("merror");
    merror.attributes.set("data-mjx-message", message);
    if (options2.fullErrors || short) {
      const mtext = this.factory.create("mtext");
      const text = this.factory.create("text");
      text.setText(options2.fullErrors ? message : this.kind);
      mtext.appendChild(text);
      merror.appendChild(mtext);
      this.parent.replaceChild(merror, this);
      if (!options2.fullErrors) {
        merror.attributes.set("title", message);
      }
    } else {
      this.parent.replaceChild(merror, this);
      merror.appendChild(this);
    }
    return merror;
  }
};
AbstractMmlNode.defaults = {
  mathbackground: INHERIT,
  mathcolor: INHERIT,
  mathsize: INHERIT,
  dir: INHERIT
};
AbstractMmlNode.noInherit = {
  mstyle: {
    mpadded: {
      width: true,
      height: true,
      depth: true,
      lspace: true,
      voffset: true
    },
    mtable: { width: true, height: true, depth: true, align: true }
  },
  maligngroup: {
    mrow: { groupalign: true },
    mtable: { groupalign: true }
  },
  mtr: {
    msqrt: { "data-vertical-align": true },
    mroot: { "data-vertical-align": true }
  },
  mlabeledtr: {
    msqrt: { "data-vertical-align": true },
    mroot: { "data-vertical-align": true }
  }
};
AbstractMmlNode.stopInherit = {
  mtd: { columnalign: true, rowalign: true, groupalign: true }
};
AbstractMmlNode.alwaysInherit = {
  scriptminsize: true,
  scriptsizemultiplier: true,
  infixlinebreakstyle: true
};
AbstractMmlNode.verifyDefaults = {
  checkArity: true,
  checkAttributes: false,
  checkMathvariants: true,
  fullErrors: false,
  fixMmultiscripts: true,
  fixMtables: true
};
var AbstractMmlTokenNode = class extends AbstractMmlNode {
  get isToken() {
    return true;
  }
  get isEmpty() {
    for (const child of this.childNodes) {
      if (!(child instanceof TextNode) || child.getText().length) {
        return false;
      }
    }
    return true;
  }
  getText() {
    let text = "";
    for (const child of this.childNodes) {
      if (child instanceof TextNode) {
        text += child.getText();
      } else if ("textContent" in child) {
        text += child.textContent();
      }
    }
    return text;
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    for (const child of this.childNodes) {
      if (child instanceof AbstractMmlNode) {
        child.setInheritedAttributes(attributes, display, level, prime);
      }
    }
  }
  walkTree(func, data) {
    func(this, data);
    for (const child of this.childNodes) {
      if (child instanceof AbstractMmlNode) {
        child.walkTree(func, data);
      }
    }
    return data;
  }
};
AbstractMmlTokenNode.defaults = Object.assign(Object.assign({}, AbstractMmlNode.defaults), { mathvariant: "normal", mathsize: INHERIT });
var AbstractMmlLayoutNode = class extends AbstractMmlNode {
  get isSpacelike() {
    return this.childNodes[0].isSpacelike;
  }
  get isEmbellished() {
    return this.childNodes[0].isEmbellished;
  }
  get arity() {
    return -1;
  }
  core() {
    return this.childNodes[0];
  }
  coreMO() {
    return this.childNodes[0].coreMO();
  }
  setTeXclass(prev) {
    prev = this.childNodes[0].setTeXclass(prev);
    this.updateTeXclass(this.childNodes[0]);
    return prev;
  }
};
AbstractMmlLayoutNode.defaults = AbstractMmlNode.defaults;
var AbstractMmlBaseNode = class extends AbstractMmlNode {
  get isEmbellished() {
    return this.childNodes[0].isEmbellished;
  }
  core() {
    return this.childNodes[0];
  }
  coreMO() {
    return this.childNodes[0].coreMO();
  }
  setTeXclass(prev) {
    this.getPrevClass(prev);
    this.texClass = TEXCLASS.ORD;
    const base = this.childNodes[0];
    let result = null;
    if (base) {
      if (this.isEmbellished || base.isKind("mi")) {
        result = base.setTeXclass(prev);
        this.updateTeXclass(this.core());
      } else {
        base.setTeXclass(null);
        if (base.isKind("TeXAtom")) {
          this.texClass = base.texClass;
        }
      }
    }
    for (const child of this.childNodes.slice(1)) {
      if (child) {
        child.setTeXclass(null);
      }
    }
    return result || this;
  }
};
AbstractMmlBaseNode.defaults = AbstractMmlNode.defaults;
var AbstractMmlEmptyNode = class extends AbstractEmptyNode {
  get isToken() {
    return false;
  }
  get isEmpty() {
    return true;
  }
  get isEmbellished() {
    return false;
  }
  get isSpacelike() {
    return false;
  }
  get linebreakContainer() {
    return false;
  }
  get linebreakAlign() {
    return "";
  }
  get arity() {
    return 0;
  }
  get isInferred() {
    return false;
  }
  get notParent() {
    return false;
  }
  get Parent() {
    return this.parent;
  }
  get texClass() {
    return TEXCLASS.NONE;
  }
  get prevClass() {
    return TEXCLASS.NONE;
  }
  get prevLevel() {
    return 0;
  }
  hasSpacingAttributes() {
    return false;
  }
  get attributes() {
    return null;
  }
  core() {
    return this;
  }
  coreMO() {
    return this;
  }
  coreIndex() {
    return 0;
  }
  childPosition() {
    return 0;
  }
  setTeXclass(prev) {
    return prev;
  }
  texSpacing() {
    return "";
  }
  setInheritedAttributes(_attributes, _display, _level, _prime) {
  }
  inheritAttributesFrom(_node) {
  }
  verifyTree(_options) {
  }
  mError(_message, _options, _short = false) {
    return null;
  }
};
var TextNode = class extends AbstractMmlEmptyNode {
  constructor() {
    super(...arguments);
    this.text = "";
  }
  get kind() {
    return "text";
  }
  getText() {
    return this.text;
  }
  setText(text) {
    this.text = text;
    return this;
  }
  copy() {
    return this.factory.create(this.kind).setText(this.getText());
  }
  toString() {
    return this.text;
  }
};
var XMLNode = class extends AbstractMmlEmptyNode {
  constructor() {
    super(...arguments);
    this.xml = null;
    this.adaptor = null;
  }
  get kind() {
    return "XML";
  }
  getXML() {
    return this.xml;
  }
  setXML(xml, adaptor2 = null) {
    this.xml = xml;
    this.adaptor = adaptor2;
    return this;
  }
  getSerializedXML() {
    return this.adaptor.serializeXML(this.xml);
  }
  copy() {
    return this.factory.create(this.kind).setXML(this.adaptor.clone(this.xml));
  }
  toString() {
    return "XML data";
  }
};

// node_modules/@mathjax/src/mjs/core/MmlTree/OperatorDictionary.js
function OPDEF(lspace, rspace, texClass = TEXCLASS.BIN, properties = null) {
  return [lspace, rspace, texClass, properties];
}
var MO = {
  REL: OPDEF(5, 5, TEXCLASS.REL),
  WIDEREL: OPDEF(5, 5, TEXCLASS.REL, { accent: true, stretchy: true }),
  BIN4: OPDEF(4, 4, TEXCLASS.BIN),
  RELSTRETCH: OPDEF(5, 5, TEXCLASS.REL, { stretchy: true }),
  ORD: OPDEF(0, 0, TEXCLASS.ORD),
  BIN3: OPDEF(3, 3, TEXCLASS.BIN),
  OPEN: OPDEF(0, 0, TEXCLASS.OPEN, {
    fence: true,
    stretchy: true,
    symmetric: true
  }),
  CLOSE: OPDEF(0, 0, TEXCLASS.CLOSE, {
    fence: true,
    stretchy: true,
    symmetric: true
  }),
  INTEGRAL: OPDEF(3, 3, TEXCLASS.OP, { largeop: true, symmetric: true }),
  ACCENT: OPDEF(0, 0, TEXCLASS.ORD, { accent: true }),
  WIDEACCENT: OPDEF(0, 0, TEXCLASS.ORD, { accent: true, stretchy: true }),
  OP: OPDEF(3, 3, TEXCLASS.OP, {
    largeop: true,
    movablelimits: true,
    symmetric: true
  }),
  RELACCENT: OPDEF(5, 5, TEXCLASS.REL, { accent: true }),
  BIN0: OPDEF(0, 0, TEXCLASS.BIN),
  BIN5: OPDEF(5, 5, TEXCLASS.BIN),
  FENCE: OPDEF(0, 0, TEXCLASS.ORD, {
    fence: true,
    stretchy: true,
    symmetric: true
  }),
  INNER: OPDEF(1, 1, TEXCLASS.INNER),
  ORD30: OPDEF(3, 0, TEXCLASS.ORD),
  NONE: OPDEF(0, 0, TEXCLASS.NONE),
  ORDSTRETCH0: OPDEF(0, 0, TEXCLASS.ORD, { stretchy: true }),
  BINSTRETCH0: OPDEF(0, 0, TEXCLASS.BIN, { stretchy: true }),
  RELSTRETCH0: OPDEF(0, 0, TEXCLASS.REL, { stretchy: true }),
  CLOSE0: OPDEF(0, 0, TEXCLASS.CLOSE, { fence: true }),
  ORD3: OPDEF(3, 3, TEXCLASS.ORD),
  PUNCT03: OPDEF(0, 3, TEXCLASS.PUNCT, { linebreakstyle: "after" }),
  OPEN0: OPDEF(0, 0, TEXCLASS.OPEN, { fence: true }),
  STRETCH4: OPDEF(4, 4, TEXCLASS.BIN, { stretchy: true })
};
var RANGES = [
  [32, 127, TEXCLASS.REL, "mo"],
  [160, 191, TEXCLASS.ORD, "mo"],
  [192, 591, TEXCLASS.ORD, "mi"],
  [688, 879, TEXCLASS.ORD, "mo"],
  [880, 6688, TEXCLASS.ORD, "mi"],
  [6832, 6911, TEXCLASS.ORD, "mo"],
  [6912, 7615, TEXCLASS.ORD, "mi"],
  [7616, 7679, TEXCLASS.ORD, "mo"],
  [7680, 8191, TEXCLASS.ORD, "mi"],
  [8192, 8303, TEXCLASS.ORD, "mo"],
  [8304, 8351, TEXCLASS.ORD, "mo"],
  [8448, 8527, TEXCLASS.ORD, "mi"],
  [8528, 8591, TEXCLASS.ORD, "mn"],
  [8592, 8703, TEXCLASS.REL, "mo"],
  [8704, 8959, TEXCLASS.BIN, "mo"],
  [8960, 9215, TEXCLASS.ORD, "mo"],
  [9312, 9471, TEXCLASS.ORD, "mn"],
  [9472, 10223, TEXCLASS.ORD, "mo"],
  [10224, 10239, TEXCLASS.REL, "mo"],
  [10240, 10495, TEXCLASS.ORD, "mtext"],
  [10496, 10623, TEXCLASS.REL, "mo"],
  [10624, 10751, TEXCLASS.ORD, "mo"],
  [10752, 11007, TEXCLASS.BIN, "mo"],
  [11008, 11055, TEXCLASS.ORD, "mo"],
  [11056, 11087, TEXCLASS.REL, "mo"],
  [11088, 11263, TEXCLASS.ORD, "mo"],
  [11264, 11744, TEXCLASS.ORD, "mi"],
  [11776, 11903, TEXCLASS.ORD, "mo"],
  [11904, 12255, TEXCLASS.ORD, "mi", "normal"],
  [12272, 12351, TEXCLASS.ORD, "mo"],
  [12352, 42143, TEXCLASS.ORD, "mi", "normal"],
  [42192, 43055, TEXCLASS.ORD, "mi"],
  [43056, 43071, TEXCLASS.ORD, "mn"],
  [43072, 55295, TEXCLASS.ORD, "mi"],
  [63744, 64255, TEXCLASS.ORD, "mi", "normal"],
  [64256, 65023, TEXCLASS.ORD, "mi"],
  [65024, 65135, TEXCLASS.ORD, "mo"],
  [65136, 65791, TEXCLASS.ORD, "mi"],
  [65792, 65935, TEXCLASS.ORD, "mn"],
  [65936, 74751, TEXCLASS.ORD, "mi", "normal"],
  [74752, 74879, TEXCLASS.ORD, "mn"],
  [74880, 113823, TEXCLASS.ORD, "mi", "normal"],
  [113824, 119391, TEXCLASS.ORD, "mo"],
  [119648, 119679, TEXCLASS.ORD, "mn"],
  [119808, 120781, TEXCLASS.ORD, "mi"],
  [120782, 120831, TEXCLASS.ORD, "mn"],
  [122624, 129023, TEXCLASS.ORD, "mo"],
  [129024, 129279, TEXCLASS.REL, "mo"],
  [129280, 129535, TEXCLASS.ORD, "mo"],
  [131072, 195103, TEXCLASS.ORD, "mi", "normal"]
];
function getRange(text) {
  const def = OPTABLE.infix[text] || OPTABLE.prefix[text] || OPTABLE.postfix[text];
  if (def) {
    return [0, 0, def[2], "mo"];
  }
  const n = text.codePointAt(0);
  for (const range of RANGES) {
    if (n <= range[1]) {
      if (n >= range[0]) {
        return range;
      }
      break;
    }
  }
  return [0, 0, TEXCLASS.REL, "mo"];
}
var MMLSPACING = [
  [0, 0],
  [1, 2],
  [3, 3],
  [4, 4],
  [0, 0],
  [0, 0],
  [0, 3],
  [1, 1]
];
var OPTABLE = {
  prefix: {
    "!": MO.ORD,
    "(": MO.OPEN,
    "+": MO.BIN0,
    "-": MO.BIN0,
    "[": MO.OPEN,
    "{": MO.OPEN,
    "|": MO.OPEN,
    "||": MO.BIN0,
    "\xAC": MO.ORD,
    "\xB1": MO.BIN0,
    "\u2016": MO.FENCE,
    "\u2018": MO.OPEN0,
    "\u201C": MO.OPEN0,
    "\u2145": MO.ORD30,
    "\u2146": MO.ORD30,
    "\u2200": MO.ORD,
    "\u2201": MO.ORD,
    "\u2202": MO.ORD30,
    "\u2203": MO.ORD,
    "\u2204": MO.ORD,
    "\u2207": MO.ORD,
    "\u220F": MO.OP,
    "\u2210": MO.OP,
    "\u2211": MO.OP,
    "\u2212": MO.BIN0,
    "\u2213": MO.BIN0,
    "\u221A": [3, 0, TEXCLASS.ORD, { stretchy: true }],
    "\u221B": MO.ORD30,
    "\u221C": MO.ORD30,
    "\u221F": MO.ORD,
    "\u2220": MO.ORD,
    "\u2221": MO.ORD,
    "\u2222": MO.ORD,
    "\u222B": MO.INTEGRAL,
    "\u222C": MO.INTEGRAL,
    "\u222D": MO.INTEGRAL,
    "\u222E": MO.INTEGRAL,
    "\u222F": MO.INTEGRAL,
    "\u2230": MO.INTEGRAL,
    "\u2231": MO.INTEGRAL,
    "\u2232": MO.INTEGRAL,
    "\u2233": MO.INTEGRAL,
    "\u2234": MO.REL,
    "\u2235": MO.REL,
    "\u223C": [0, 0, TEXCLASS.REL, {}],
    "\u22BE": MO.ORD,
    "\u22BF": MO.ORD,
    "\u22C0": MO.OP,
    "\u22C1": MO.OP,
    "\u22C2": MO.OP,
    "\u22C3": MO.OP,
    "\u2308": MO.OPEN,
    "\u230A": MO.OPEN,
    "\u2310": MO.ORD,
    "\u2319": MO.ORD,
    "\u2772": MO.OPEN,
    "\u2795": MO.ORD,
    "\u2796": MO.ORD,
    "\u27C0": MO.ORD,
    "\u27E6": MO.OPEN,
    "\u27E8": MO.OPEN,
    "\u27EA": MO.OPEN,
    "\u27EC": MO.OPEN,
    "\u27EE": MO.OPEN,
    "\u2980": MO.FENCE,
    "\u2983": MO.OPEN,
    "\u2985": MO.OPEN,
    "\u2987": MO.OPEN,
    "\u2989": MO.OPEN,
    "\u298B": MO.OPEN,
    "\u298D": MO.OPEN,
    "\u298F": MO.OPEN,
    "\u2991": MO.OPEN,
    "\u2993": MO.OPEN,
    "\u2995": MO.OPEN,
    "\u2997": MO.OPEN,
    "\u2999": MO.FENCE,
    "\u299B": MO.ORD,
    "\u299C": MO.ORD,
    "\u299D": MO.ORD,
    "\u299E": MO.ORD,
    "\u299F": MO.ORD,
    "\u29A0": MO.ORD,
    "\u29A1": MO.ORD,
    "\u29A2": MO.ORD,
    "\u29A3": MO.ORD,
    "\u29A4": MO.ORD,
    "\u29A5": MO.ORD,
    "\u29A6": MO.ORD,
    "\u29A7": MO.ORD,
    "\u29A8": MO.ORD,
    "\u29A9": MO.ORD,
    "\u29AA": MO.ORD,
    "\u29AB": MO.ORD,
    "\u29AC": MO.ORD,
    "\u29AD": MO.ORD,
    "\u29AE": MO.ORD,
    "\u29AF": MO.ORD,
    "\u29D8": MO.OPEN,
    "\u29DA": MO.OPEN,
    "\u29FC": MO.OPEN,
    "\u2A00": MO.OP,
    "\u2A01": MO.OP,
    "\u2A02": MO.OP,
    "\u2A03": MO.OP,
    "\u2A04": MO.OP,
    "\u2A05": MO.OP,
    "\u2A06": MO.OP,
    "\u2A07": MO.OP,
    "\u2A08": MO.OP,
    "\u2A09": MO.OP,
    "\u2A0A": MO.OP,
    "\u2A0B": MO.INTEGRAL,
    "\u2A0C": MO.INTEGRAL,
    "\u2A0D": MO.INTEGRAL,
    "\u2A0E": MO.INTEGRAL,
    "\u2A0F": MO.INTEGRAL,
    "\u2A10": MO.INTEGRAL,
    "\u2A11": MO.INTEGRAL,
    "\u2A12": MO.INTEGRAL,
    "\u2A13": MO.INTEGRAL,
    "\u2A14": MO.INTEGRAL,
    "\u2A15": MO.INTEGRAL,
    "\u2A16": MO.INTEGRAL,
    "\u2A17": MO.INTEGRAL,
    "\u2A18": MO.INTEGRAL,
    "\u2A19": MO.INTEGRAL,
    "\u2A1A": MO.INTEGRAL,
    "\u2A1B": MO.INTEGRAL,
    "\u2A1C": MO.INTEGRAL,
    "\u2A1D": MO.OP,
    "\u2A1E": MO.OP,
    "\u2AEC": MO.ORD,
    "\u2AED": MO.ORD,
    "\u2AFC": MO.OP,
    "\u2AFF": MO.OP,
    "\u3008": MO.OPEN
  },
  postfix: {
    "!!": MO.BIN0,
    "!": MO.CLOSE0,
    '"': MO.ORD,
    "%": MO.ORD,
    "&": MO.ORD,
    "'": MO.ACCENT,
    ")": MO.CLOSE,
    "++": MO.BIN0,
    "--": MO.BIN0,
    "]": MO.CLOSE,
    "^": MO.WIDEACCENT,
    "_": MO.WIDEACCENT,
    "`": MO.ACCENT,
    "|": MO.CLOSE,
    "||": MO.BIN0,
    "}": MO.CLOSE,
    "~": MO.WIDEACCENT,
    "\xA8": MO.ACCENT,
    "\xAF": MO.WIDEACCENT,
    "\xB0": MO.ACCENT,
    "\xB2": MO.ORD,
    "\xB3": MO.ORD,
    "\xB4": MO.ACCENT,
    "\xB8": MO.ACCENT,
    "\xB9": MO.ORD,
    "\u02C6": MO.WIDEACCENT,
    "\u02C7": MO.WIDEACCENT,
    "\u02C9": MO.WIDEACCENT,
    "\u02CA": MO.ACCENT,
    "\u02CB": MO.ACCENT,
    "\u02CD": MO.WIDEACCENT,
    "\u02D8": MO.ACCENT,
    "\u02D9": MO.ACCENT,
    "\u02DA": MO.ACCENT,
    "\u02DC": MO.WIDEACCENT,
    "\u02DD": MO.ACCENT,
    "\u02F7": MO.WIDEACCENT,
    "\u0302": MO.WIDEACCENT,
    "\u0311": MO.ACCENT,
    "\u2016": MO.FENCE,
    "\u2019": MO.CLOSE0,
    "\u201A": MO.ORD,
    "\u201B": MO.ORD,
    "\u201D": MO.CLOSE0,
    "\u201E": MO.ORD,
    "\u201F": MO.ORD,
    "\u2032": MO.ORD,
    "\u2033": MO.ORD,
    "\u2034": MO.ORD,
    "\u2035": MO.ORD,
    "\u2036": MO.ORD,
    "\u2037": MO.ORD,
    "\u203E": MO.WIDEACCENT,
    "\u2057": MO.ORD,
    "\u20DB": MO.ACCENT,
    "\u20DC": MO.ACCENT,
    "\u2309": MO.CLOSE,
    "\u230B": MO.CLOSE,
    "\u2322": MO.RELSTRETCH0,
    "\u2323": MO.RELSTRETCH0,
    "\u23B4": MO.WIDEACCENT,
    "\u23B5": MO.WIDEACCENT,
    "\u23CD": MO.ORD,
    "\u23DC": MO.WIDEACCENT,
    "\u23DD": MO.WIDEACCENT,
    "\u23DE": MO.WIDEACCENT,
    "\u23DF": MO.WIDEACCENT,
    "\u23E0": MO.WIDEACCENT,
    "\u23E1": MO.WIDEACCENT,
    "\u2773": MO.CLOSE,
    "\u27E7": MO.CLOSE,
    "\u27E9": MO.CLOSE,
    "\u27EB": MO.CLOSE,
    "\u27ED": MO.CLOSE,
    "\u27EF": MO.CLOSE,
    "\u2980": MO.FENCE,
    "\u2984": MO.CLOSE,
    "\u2986": MO.CLOSE,
    "\u2988": MO.CLOSE,
    "\u298A": MO.CLOSE,
    "\u298C": MO.CLOSE,
    "\u298E": MO.CLOSE,
    "\u2990": MO.CLOSE,
    "\u2992": MO.CLOSE,
    "\u2994": MO.CLOSE,
    "\u2996": MO.CLOSE,
    "\u2998": MO.CLOSE,
    "\u2999": MO.FENCE,
    "\u29D9": MO.CLOSE,
    "\u29DB": MO.CLOSE,
    "\u29FD": MO.CLOSE,
    "\u3009": MO.CLOSE,
    "\u{1EEF0}": MO.BINSTRETCH0,
    "\u{1EEF1}": MO.BINSTRETCH0
  },
  infix: {
    "!": MO.ORD,
    "!=": MO.BIN5,
    "#": MO.ORD,
    "$": MO.ORD,
    "%": MO.ORD3,
    "&&": MO.BIN4,
    "**": MO.BIN3,
    "*": MO.BIN3,
    "*=": MO.BIN5,
    "+": MO.BIN4,
    "+=": MO.BIN5,
    ",": MO.PUNCT03,
    "": MO.ORD,
    "-": MO.BIN4,
    "-=": MO.BIN5,
    "->": MO.BIN5,
    ".": MO.ORD3,
    "..": MO.BIN3,
    "...": MO.INNER,
    "/": [4, 4, TEXCLASS.ORD, {}],
    "//": MO.BIN5,
    "/=": MO.BIN5,
    ":": [0, 3, TEXCLASS.REL, {}],
    ":=": MO.BIN5,
    ";": MO.PUNCT03,
    "<": MO.REL,
    "<=": MO.REL,
    "<>": [3, 3, TEXCLASS.REL, {}],
    "=": MO.REL,
    "==": MO.REL,
    ">": MO.REL,
    ">=": MO.REL,
    "?": [3, 3, TEXCLASS.CLOSE, { fence: true }],
    "@": MO.ORD3,
    "\\": MO.ORD,
    "^": [3, 3, TEXCLASS.ORD, { accent: true, stretchy: true }],
    "_": MO.WIDEACCENT,
    "|": [5, 5, TEXCLASS.ORD, {}],
    "||": MO.BIN5,
    "\xB1": MO.BIN4,
    "\xB7": MO.BIN3,
    "\xD7": MO.BIN3,
    "\xF7": MO.BIN4,
    "\u02B9": MO.ORD,
    "\u0300": MO.ACCENT,
    "\u0301": MO.ACCENT,
    "\u0303": MO.WIDEACCENT,
    "\u0304": MO.ACCENT,
    "\u0306": MO.ACCENT,
    "\u0307": MO.ACCENT,
    "\u0308": MO.ACCENT,
    "\u030C": MO.ACCENT,
    "\u0332": MO.WIDEACCENT,
    "\u0338": MO.REL,
    "\u03F6": MO.REL,
    "\u2015": MO.ORDSTRETCH0,
    "\u2017": MO.ORDSTRETCH0,
    "\u2020": MO.BIN3,
    "\u2021": MO.BIN3,
    "\u2022": MO.BIN3,
    "\u2026": MO.INNER,
    "\u2043": MO.BIN3,
    "\u2044": MO.STRETCH4,
    "\u2061": MO.NONE,
    "\u2062": MO.NONE,
    "\u2063": [0, 0, TEXCLASS.NONE, { linebreakstyle: "after" }],
    "\u2064": MO.NONE,
    "\u20D7": MO.ACCENT,
    "\u2111": MO.ORD,
    "\u2113": MO.ORD,
    "\u2118": MO.ORD,
    "\u211C": MO.ORD,
    "\u2190": MO.WIDEREL,
    "\u2191": MO.RELSTRETCH,
    "\u2192": MO.WIDEREL,
    "\u2193": MO.RELSTRETCH,
    "\u2194": MO.WIDEREL,
    "\u2195": MO.RELSTRETCH,
    "\u2196": MO.REL,
    "\u2197": MO.REL,
    "\u2198": MO.REL,
    "\u2199": MO.REL,
    "\u219A": MO.WIDEREL,
    "\u219B": MO.WIDEREL,
    "\u219C": MO.WIDEREL,
    "\u219D": MO.WIDEREL,
    "\u219E": MO.WIDEREL,
    "\u219F": MO.RELSTRETCH,
    "\u21A0": MO.WIDEREL,
    "\u21A1": MO.RELSTRETCH,
    "\u21A2": MO.WIDEREL,
    "\u21A3": MO.WIDEREL,
    "\u21A4": MO.WIDEREL,
    "\u21A5": MO.RELSTRETCH,
    "\u21A6": MO.WIDEREL,
    "\u21A7": MO.RELSTRETCH,
    "\u21A8": MO.RELSTRETCH,
    "\u21A9": MO.WIDEREL,
    "\u21AA": MO.WIDEREL,
    "\u21AB": MO.WIDEREL,
    "\u21AC": MO.WIDEREL,
    "\u21AD": MO.WIDEREL,
    "\u21AE": MO.WIDEREL,
    "\u21AF": MO.REL,
    "\u21B0": MO.RELSTRETCH,
    "\u21B1": MO.RELSTRETCH,
    "\u21B2": MO.RELSTRETCH,
    "\u21B3": MO.RELSTRETCH,
    "\u21B4": MO.RELSTRETCH,
    "\u21B5": MO.RELSTRETCH,
    "\u21B6": MO.REL,
    "\u21B7": MO.REL,
    "\u21B8": MO.REL,
    "\u21B9": MO.WIDEREL,
    "\u21BA": MO.REL,
    "\u21BB": MO.REL,
    "\u21BC": MO.WIDEREL,
    "\u21BD": MO.WIDEREL,
    "\u21BE": MO.RELSTRETCH,
    "\u21BF": MO.RELSTRETCH,
    "\u21C0": MO.WIDEREL,
    "\u21C1": MO.WIDEREL,
    "\u21C2": MO.RELSTRETCH,
    "\u21C3": MO.RELSTRETCH,
    "\u21C4": MO.WIDEREL,
    "\u21C5": MO.RELSTRETCH,
    "\u21C6": MO.WIDEREL,
    "\u21C7": MO.WIDEREL,
    "\u21C8": MO.RELSTRETCH,
    "\u21C9": MO.WIDEREL,
    "\u21CA": MO.RELSTRETCH,
    "\u21CB": MO.WIDEREL,
    "\u21CC": MO.WIDEREL,
    "\u21CD": MO.WIDEREL,
    "\u21CE": MO.WIDEREL,
    "\u21CF": MO.WIDEREL,
    "\u21D0": MO.WIDEREL,
    "\u21D1": MO.RELSTRETCH,
    "\u21D2": MO.WIDEREL,
    "\u21D3": MO.RELSTRETCH,
    "\u21D4": MO.WIDEREL,
    "\u21D5": MO.RELSTRETCH,
    "\u21D6": MO.REL,
    "\u21D7": MO.REL,
    "\u21D8": MO.REL,
    "\u21D9": MO.REL,
    "\u21DA": MO.WIDEREL,
    "\u21DB": MO.WIDEREL,
    "\u21DC": MO.WIDEREL,
    "\u21DD": MO.WIDEREL,
    "\u21DE": MO.RELSTRETCH,
    "\u21DF": MO.RELSTRETCH,
    "\u21E0": MO.WIDEREL,
    "\u21E1": MO.RELSTRETCH,
    "\u21E2": MO.WIDEREL,
    "\u21E3": MO.RELSTRETCH,
    "\u21E4": MO.WIDEREL,
    "\u21E5": MO.WIDEREL,
    "\u21E6": MO.WIDEREL,
    "\u21E7": MO.RELSTRETCH,
    "\u21E8": MO.WIDEREL,
    "\u21E9": MO.RELSTRETCH,
    "\u21EA": MO.RELSTRETCH,
    "\u21EB": MO.RELSTRETCH,
    "\u21EC": MO.RELSTRETCH,
    "\u21ED": MO.RELSTRETCH,
    "\u21EE": MO.RELSTRETCH,
    "\u21EF": MO.RELSTRETCH,
    "\u21F0": MO.WIDEREL,
    "\u21F1": MO.REL,
    "\u21F2": MO.REL,
    "\u21F3": MO.RELSTRETCH,
    "\u21F4": MO.WIDEREL,
    "\u21F5": MO.RELSTRETCH,
    "\u21F6": MO.WIDEREL,
    "\u21F7": MO.WIDEREL,
    "\u21F8": MO.WIDEREL,
    "\u21F9": MO.WIDEREL,
    "\u21FA": MO.WIDEREL,
    "\u21FB": MO.WIDEREL,
    "\u21FC": MO.WIDEREL,
    "\u21FD": MO.WIDEREL,
    "\u21FE": MO.WIDEREL,
    "\u21FF": MO.WIDEREL,
    "\u2205": MO.ORD,
    "\u2206": MO.ORD,
    "\u2208": MO.REL,
    "\u2209": MO.REL,
    "\u220A": MO.REL,
    "\u220B": MO.REL,
    "\u220C": MO.REL,
    "\u220D": MO.REL,
    "\u2212": MO.BIN4,
    "\u2213": MO.BIN4,
    "\u2214": MO.BIN4,
    "\u2215": MO.STRETCH4,
    "\u2216": MO.BIN4,
    "\u2217": MO.BIN3,
    "\u2218": MO.BIN3,
    "\u2219": MO.BIN3,
    "\u221D": MO.REL,
    "\u221E": MO.ORD,
    "\u2223": MO.REL,
    "\u2224": MO.REL,
    "\u2225": MO.REL,
    "\u2226": MO.REL,
    "\u2227": MO.BIN4,
    "\u2228": MO.BIN4,
    "\u2229": MO.BIN4,
    "\u222A": MO.BIN4,
    "\u2236": MO.BIN4,
    "\u2237": MO.REL,
    "\u2238": MO.BIN4,
    "\u2239": MO.REL,
    "\u223A": MO.REL,
    "\u223B": MO.REL,
    "\u223C": MO.REL,
    "\u223D": MO.REL,
    "\u223E": MO.REL,
    "\u2240": MO.BIN3,
    "\u2241": MO.REL,
    "\u2242": MO.REL,
    "\u2242\u0338": MO.REL,
    "\u2243": MO.REL,
    "\u2244": MO.REL,
    "\u2245": MO.REL,
    "\u2246": MO.REL,
    "\u2247": MO.REL,
    "\u2248": MO.REL,
    "\u2249": MO.REL,
    "\u224A": MO.REL,
    "\u224B": MO.REL,
    "\u224C": MO.REL,
    "\u224D": MO.REL,
    "\u224E": MO.REL,
    "\u224F": MO.REL,
    "\u2250": MO.REL,
    "\u2251": MO.REL,
    "\u2252": MO.REL,
    "\u2253": MO.REL,
    "\u2254": MO.REL,
    "\u2255": MO.REL,
    "\u2256": MO.REL,
    "\u2257": MO.REL,
    "\u2258": MO.REL,
    "\u2259": MO.REL,
    "\u225A": MO.REL,
    "\u225B": MO.REL,
    "\u225C": MO.REL,
    "\u225D": MO.REL,
    "\u225E": MO.REL,
    "\u225F": MO.REL,
    "\u2260": MO.REL,
    "\u2261": MO.REL,
    "\u2262": MO.REL,
    "\u2263": MO.REL,
    "\u2264": MO.REL,
    "\u2265": MO.REL,
    "\u2266": MO.REL,
    "\u2266\u0338": MO.REL,
    "\u2267": MO.REL,
    "\u2267\u0338": MO.REL,
    "\u2268": MO.REL,
    "\u2269": MO.REL,
    "\u226A": MO.REL,
    "\u226A\u0338": MO.REL,
    "\u226B": MO.REL,
    "\u226B\u0338": MO.REL,
    "\u226C": MO.REL,
    "\u226D": MO.REL,
    "\u226E": MO.REL,
    "\u226F": MO.REL,
    "\u2270": MO.REL,
    "\u2271": MO.REL,
    "\u2272": MO.REL,
    "\u2273": MO.REL,
    "\u2274": MO.REL,
    "\u2275": MO.REL,
    "\u2276": MO.REL,
    "\u2277": MO.REL,
    "\u2278": MO.REL,
    "\u2279": MO.REL,
    "\u227A": MO.REL,
    "\u227B": MO.REL,
    "\u227C": MO.REL,
    "\u227D": MO.REL,
    "\u227E": MO.REL,
    "\u227E\u0338": MO.REL,
    "\u227F": MO.REL,
    "\u227F\u0338": MO.REL,
    "\u2280": MO.REL,
    "\u2281": MO.REL,
    "\u2282": MO.REL,
    "\u2283": MO.REL,
    "\u2284": MO.REL,
    "\u2285": MO.REL,
    "\u2286": MO.REL,
    "\u2287": MO.REL,
    "\u2288": MO.REL,
    "\u2289": MO.REL,
    "\u228A": MO.REL,
    "\u228B": MO.REL,
    "\u228C": MO.BIN4,
    "\u228D": MO.BIN4,
    "\u228E": MO.BIN4,
    "\u228F": MO.REL,
    "\u228F\u0338": MO.REL,
    "\u2290": MO.REL,
    "\u2290\u0338": MO.REL,
    "\u2291": MO.REL,
    "\u2292": MO.REL,
    "\u2293": MO.BIN4,
    "\u2294": MO.BIN4,
    "\u2295": MO.BIN4,
    "\u2296": MO.BIN4,
    "\u2297": MO.BIN3,
    "\u2298": MO.BIN4,
    "\u2299": MO.BIN3,
    "\u229A": MO.BIN3,
    "\u229B": MO.BIN3,
    "\u229C": MO.REL,
    "\u229D": MO.BIN4,
    "\u229E": MO.BIN4,
    "\u229F": MO.BIN4,
    "\u22A0": MO.BIN3,
    "\u22A1": MO.BIN3,
    "\u22A2": MO.REL,
    "\u22A3": MO.REL,
    "\u22A4": MO.ORD,
    "\u22A5": MO.ORD,
    "\u22A6": MO.REL,
    "\u22A7": MO.REL,
    "\u22A8": MO.REL,
    "\u22A9": MO.REL,
    "\u22AA": MO.REL,
    "\u22AB": MO.REL,
    "\u22AC": MO.REL,
    "\u22AD": MO.REL,
    "\u22AE": MO.REL,
    "\u22AF": MO.REL,
    "\u22B0": MO.REL,
    "\u22B1": MO.REL,
    "\u22B2": MO.REL,
    "\u22B3": MO.REL,
    "\u22B4": MO.REL,
    "\u22B5": MO.REL,
    "\u22B6": MO.REL,
    "\u22B7": MO.REL,
    "\u22B8": MO.REL,
    "\u22BA": MO.BIN3,
    "\u22BB": MO.BIN4,
    "\u22BC": MO.BIN4,
    "\u22BD": MO.BIN4,
    "\u22C4": MO.BIN3,
    "\u22C5": MO.BIN3,
    "\u22C6": MO.BIN3,
    "\u22C7": MO.BIN3,
    "\u22C8": MO.REL,
    "\u22C9": MO.BIN3,
    "\u22CA": MO.BIN3,
    "\u22CB": MO.BIN3,
    "\u22CC": MO.BIN3,
    "\u22CD": MO.REL,
    "\u22CE": MO.BIN4,
    "\u22CF": MO.BIN4,
    "\u22D0": MO.REL,
    "\u22D1": MO.REL,
    "\u22D2": MO.BIN4,
    "\u22D3": MO.BIN4,
    "\u22D4": MO.REL,
    "\u22D5": MO.REL,
    "\u22D6": MO.REL,
    "\u22D7": MO.REL,
    "\u22D8": MO.REL,
    "\u22D9": MO.REL,
    "\u22DA": MO.REL,
    "\u22DB": MO.REL,
    "\u22DC": MO.REL,
    "\u22DD": MO.REL,
    "\u22DE": MO.REL,
    "\u22DF": MO.REL,
    "\u22E0": MO.REL,
    "\u22E1": MO.REL,
    "\u22E2": MO.REL,
    "\u22E3": MO.REL,
    "\u22E4": MO.REL,
    "\u22E5": MO.REL,
    "\u22E6": MO.REL,
    "\u22E7": MO.REL,
    "\u22E8": MO.REL,
    "\u22E9": MO.REL,
    "\u22EA": MO.REL,
    "\u22EB": MO.REL,
    "\u22EC": MO.REL,
    "\u22ED": MO.REL,
    "\u22EE": MO.ORD,
    "\u22EF": MO.INNER,
    "\u22F0": MO.INNER,
    "\u22F1": MO.INNER,
    "\u22F2": MO.REL,
    "\u22F3": MO.REL,
    "\u22F4": MO.REL,
    "\u22F5": MO.REL,
    "\u22F6": MO.REL,
    "\u22F7": MO.REL,
    "\u22F8": MO.REL,
    "\u22F9": MO.REL,
    "\u22FA": MO.REL,
    "\u22FB": MO.REL,
    "\u22FC": MO.REL,
    "\u22FD": MO.REL,
    "\u22FE": MO.REL,
    "\u22FF": MO.REL,
    "\u2301": MO.REL,
    "\u2305": MO.BIN3,
    "\u2306": MO.BIN3,
    "\u2329": MO.OPEN,
    "\u232A": MO.CLOSE,
    "\u237C": MO.REL,
    "\u238B": MO.REL,
    "\u23AA": MO.ORD,
    "\u23AF": MO.ORDSTRETCH0,
    "\u23B0": MO.OPEN,
    "\u23B1": MO.CLOSE,
    "\u2500": MO.ORD,
    "\u25B3": MO.BIN3,
    "\u25B5": MO.BIN3,
    "\u25B9": MO.BIN3,
    "\u25BD": MO.BIN3,
    "\u25BF": MO.BIN3,
    "\u25C3": MO.BIN3,
    "\u25EF": MO.BIN3,
    "\u2660": MO.ORD,
    "\u2661": MO.ORD,
    "\u2662": MO.ORD,
    "\u2663": MO.ORD,
    "\u266D": MO.ORD,
    "\u266E": MO.ORD,
    "\u266F": MO.ORD,
    "\u2758": [5, 5, TEXCLASS.REL, { stretchy: true, symmetric: true }],
    "\u2794": MO.WIDEREL,
    "\u2795": MO.BIN4,
    "\u2796": MO.BIN4,
    "\u2797": MO.BIN4,
    "\u2798": MO.REL,
    "\u2799": MO.WIDEREL,
    "\u279A": MO.REL,
    "\u279B": MO.WIDEREL,
    "\u279C": MO.WIDEREL,
    "\u279D": MO.WIDEREL,
    "\u279E": MO.WIDEREL,
    "\u279F": MO.WIDEREL,
    "\u27A0": MO.WIDEREL,
    "\u27A1": MO.WIDEREL,
    "\u27A5": MO.WIDEREL,
    "\u27A6": MO.WIDEREL,
    "\u27A7": MO.RELACCENT,
    "\u27A8": MO.WIDEREL,
    "\u27A9": MO.WIDEREL,
    "\u27AA": MO.WIDEREL,
    "\u27AB": MO.WIDEREL,
    "\u27AC": MO.WIDEREL,
    "\u27AD": MO.WIDEREL,
    "\u27AE": MO.WIDEREL,
    "\u27AF": MO.WIDEREL,
    "\u27B1": MO.WIDEREL,
    "\u27B2": MO.RELACCENT,
    "\u27B3": MO.WIDEREL,
    "\u27B4": MO.REL,
    "\u27B5": MO.WIDEREL,
    "\u27B6": MO.REL,
    "\u27B7": MO.REL,
    "\u27B8": MO.WIDEREL,
    "\u27B9": MO.REL,
    "\u27BA": MO.WIDEREL,
    "\u27BB": MO.WIDEREL,
    "\u27BC": MO.WIDEREL,
    "\u27BD": MO.WIDEREL,
    "\u27BE": MO.WIDEREL,
    "\u27C2": MO.REL,
    "\u27C2\u0338": MO.REL,
    "\u27CB": MO.BIN3,
    "\u27CD": MO.BIN3,
    "\u27F0": MO.RELSTRETCH,
    "\u27F1": MO.RELSTRETCH,
    "\u27F2": MO.REL,
    "\u27F3": MO.REL,
    "\u27F4": MO.RELSTRETCH,
    "\u27F5": MO.WIDEREL,
    "\u27F6": MO.WIDEREL,
    "\u27F7": MO.WIDEREL,
    "\u27F8": MO.WIDEREL,
    "\u27F9": MO.WIDEREL,
    "\u27FA": MO.WIDEREL,
    "\u27FB": MO.WIDEREL,
    "\u27FC": MO.WIDEREL,
    "\u27FD": MO.WIDEREL,
    "\u27FE": MO.WIDEREL,
    "\u27FF": MO.WIDEREL,
    "\u2900": MO.WIDEREL,
    "\u2901": MO.WIDEREL,
    "\u2902": MO.WIDEREL,
    "\u2903": MO.WIDEREL,
    "\u2904": MO.WIDEREL,
    "\u2905": MO.WIDEREL,
    "\u2906": MO.WIDEREL,
    "\u2907": MO.WIDEREL,
    "\u2908": MO.RELSTRETCH,
    "\u2909": MO.RELSTRETCH,
    "\u290A": MO.RELSTRETCH,
    "\u290B": MO.RELSTRETCH,
    "\u290C": MO.WIDEREL,
    "\u290D": MO.WIDEREL,
    "\u290E": MO.WIDEREL,
    "\u290F": MO.WIDEREL,
    "\u2910": MO.WIDEREL,
    "\u2911": MO.WIDEREL,
    "\u2912": MO.RELSTRETCH,
    "\u2913": MO.RELSTRETCH,
    "\u2914": MO.WIDEREL,
    "\u2915": MO.WIDEREL,
    "\u2916": MO.WIDEREL,
    "\u2917": MO.WIDEREL,
    "\u2918": MO.WIDEREL,
    "\u2919": MO.WIDEREL,
    "\u291A": MO.WIDEREL,
    "\u291B": MO.WIDEREL,
    "\u291C": MO.WIDEREL,
    "\u291D": MO.WIDEREL,
    "\u291E": MO.WIDEREL,
    "\u291F": MO.WIDEREL,
    "\u2920": MO.WIDEREL,
    "\u2921": MO.REL,
    "\u2922": MO.REL,
    "\u2923": MO.REL,
    "\u2924": MO.REL,
    "\u2925": MO.REL,
    "\u2926": MO.REL,
    "\u2927": MO.REL,
    "\u2928": MO.REL,
    "\u2929": MO.REL,
    "\u292A": MO.REL,
    "\u292B": MO.REL,
    "\u292C": MO.REL,
    "\u292D": MO.REL,
    "\u292E": MO.REL,
    "\u292F": MO.REL,
    "\u2930": MO.REL,
    "\u2931": MO.REL,
    "\u2932": MO.REL,
    "\u2933": MO.RELACCENT,
    "\u2934": MO.RELSTRETCH,
    "\u2935": MO.RELSTRETCH,
    "\u2936": MO.RELSTRETCH,
    "\u2937": MO.RELSTRETCH,
    "\u2938": MO.REL,
    "\u2939": MO.REL,
    "\u293A": MO.RELACCENT,
    "\u293B": MO.RELACCENT,
    "\u293C": MO.RELACCENT,
    "\u293D": MO.RELACCENT,
    "\u293E": MO.REL,
    "\u293F": MO.REL,
    "\u2940": MO.REL,
    "\u2941": MO.REL,
    "\u2942": MO.WIDEREL,
    "\u2943": MO.WIDEREL,
    "\u2944": MO.WIDEREL,
    "\u2945": MO.RELSTRETCH,
    "\u2946": MO.RELSTRETCH,
    "\u2947": MO.WIDEREL,
    "\u2948": MO.WIDEREL,
    "\u2949": MO.RELSTRETCH,
    "\u294A": MO.WIDEREL,
    "\u294B": MO.WIDEREL,
    "\u294C": MO.RELSTRETCH,
    "\u294D": MO.RELSTRETCH,
    "\u294E": MO.WIDEREL,
    "\u294F": MO.RELSTRETCH,
    "\u2950": MO.WIDEREL,
    "\u2951": MO.RELSTRETCH,
    "\u2952": MO.WIDEREL,
    "\u2953": MO.WIDEREL,
    "\u2954": MO.RELSTRETCH,
    "\u2955": MO.RELSTRETCH,
    "\u2956": MO.WIDEREL,
    "\u2957": MO.WIDEREL,
    "\u2958": MO.RELSTRETCH,
    "\u2959": MO.RELSTRETCH,
    "\u295A": MO.WIDEREL,
    "\u295B": MO.WIDEREL,
    "\u295C": MO.RELSTRETCH,
    "\u295D": MO.RELSTRETCH,
    "\u295E": MO.WIDEREL,
    "\u295F": MO.WIDEREL,
    "\u2960": MO.RELSTRETCH,
    "\u2961": MO.RELSTRETCH,
    "\u2962": MO.WIDEREL,
    "\u2963": MO.RELSTRETCH,
    "\u2964": MO.WIDEREL,
    "\u2965": MO.RELSTRETCH,
    "\u2966": MO.WIDEREL,
    "\u2967": MO.WIDEREL,
    "\u2968": MO.WIDEREL,
    "\u2969": MO.WIDEREL,
    "\u296A": MO.WIDEREL,
    "\u296B": MO.WIDEREL,
    "\u296C": MO.WIDEREL,
    "\u296D": MO.WIDEREL,
    "\u296E": MO.RELSTRETCH,
    "\u296F": MO.RELSTRETCH,
    "\u2970": MO.WIDEREL,
    "\u2971": MO.WIDEREL,
    "\u2972": MO.WIDEREL,
    "\u2973": MO.WIDEREL,
    "\u2974": MO.WIDEREL,
    "\u2975": MO.WIDEREL,
    "\u2976": MO.RELACCENT,
    "\u2977": MO.RELACCENT,
    "\u2978": MO.RELACCENT,
    "\u2979": MO.RELACCENT,
    "\u297A": MO.RELACCENT,
    "\u297B": MO.RELACCENT,
    "\u297C": MO.WIDEREL,
    "\u297D": MO.WIDEREL,
    "\u297E": MO.RELSTRETCH,
    "\u297F": MO.RELSTRETCH,
    "\u2981": MO.REL,
    "\u2982": MO.REL,
    "\u29B6": MO.REL,
    "\u29B7": MO.REL,
    "\u29B8": MO.BIN4,
    "\u29B9": MO.REL,
    "\u29BC": MO.BIN4,
    "\u29C0": MO.REL,
    "\u29C1": MO.REL,
    "\u29C4": MO.BIN4,
    "\u29C5": MO.BIN4,
    "\u29C6": MO.BIN3,
    "\u29C7": MO.BIN3,
    "\u29C8": MO.BIN3,
    "\u29CE": MO.REL,
    "\u29CF": MO.REL,
    "\u29D0": MO.REL,
    "\u29D1": MO.REL,
    "\u29D2": MO.REL,
    "\u29D3": MO.REL,
    "\u29D4": MO.BIN3,
    "\u29D5": MO.BIN3,
    "\u29D6": MO.BIN3,
    "\u29D7": MO.BIN3,
    "\u29DF": MO.REL,
    "\u29E1": MO.REL,
    "\u29E2": MO.BIN3,
    "\u29E3": MO.REL,
    "\u29E4": MO.REL,
    "\u29E5": MO.REL,
    "\u29E6": MO.REL,
    "\u29F4": MO.REL,
    "\u29F5": MO.BIN4,
    "\u29F6": MO.BIN4,
    "\u29F7": MO.BIN4,
    "\u29F8": MO.BIN4,
    "\u29F9": MO.BIN4,
    "\u29FA": MO.BIN4,
    "\u29FB": MO.BIN4,
    "\u2A1D": MO.BIN3,
    "\u2A1E": MO.BIN3,
    "\u2A1F": MO.BIN4,
    "\u2A20": MO.BIN4,
    "\u2A21": MO.BIN4,
    "\u2A22": MO.BIN4,
    "\u2A23": MO.BIN4,
    "\u2A24": MO.BIN4,
    "\u2A25": MO.BIN4,
    "\u2A26": MO.BIN4,
    "\u2A27": MO.BIN4,
    "\u2A28": MO.BIN4,
    "\u2A29": MO.BIN4,
    "\u2A2A": MO.BIN4,
    "\u2A2B": MO.BIN4,
    "\u2A2C": MO.BIN4,
    "\u2A2D": MO.BIN4,
    "\u2A2E": MO.BIN4,
    "\u2A2F": MO.BIN3,
    "\u2A30": MO.BIN3,
    "\u2A31": MO.BIN3,
    "\u2A32": MO.BIN3,
    "\u2A33": MO.BIN3,
    "\u2A34": MO.BIN3,
    "\u2A35": MO.BIN3,
    "\u2A36": MO.BIN3,
    "\u2A37": MO.BIN3,
    "\u2A38": MO.BIN4,
    "\u2A39": MO.BIN4,
    "\u2A3A": MO.BIN4,
    "\u2A3B": MO.BIN3,
    "\u2A3C": MO.BIN3,
    "\u2A3D": MO.BIN3,
    "\u2A3E": MO.BIN4,
    "\u2A3F": MO.BIN3,
    "\u2A40": MO.BIN4,
    "\u2A41": MO.BIN4,
    "\u2A42": MO.BIN4,
    "\u2A43": MO.BIN4,
    "\u2A44": MO.BIN4,
    "\u2A45": MO.BIN4,
    "\u2A46": MO.BIN4,
    "\u2A47": MO.BIN4,
    "\u2A48": MO.BIN4,
    "\u2A49": MO.BIN4,
    "\u2A4A": MO.BIN4,
    "\u2A4B": MO.BIN4,
    "\u2A4C": MO.BIN4,
    "\u2A4D": MO.BIN4,
    "\u2A4E": MO.BIN4,
    "\u2A4F": MO.BIN4,
    "\u2A50": MO.BIN3,
    "\u2A51": MO.BIN4,
    "\u2A52": MO.BIN4,
    "\u2A53": MO.BIN4,
    "\u2A54": MO.BIN4,
    "\u2A55": MO.BIN4,
    "\u2A56": MO.BIN4,
    "\u2A57": MO.BIN4,
    "\u2A58": MO.BIN4,
    "\u2A59": MO.BIN4,
    "\u2A5A": MO.BIN4,
    "\u2A5B": MO.BIN4,
    "\u2A5C": MO.BIN4,
    "\u2A5D": MO.BIN4,
    "\u2A5E": MO.BIN4,
    "\u2A5F": MO.BIN4,
    "\u2A60": MO.BIN4,
    "\u2A61": MO.BIN4,
    "\u2A62": MO.BIN4,
    "\u2A63": MO.BIN4,
    "\u2A64": MO.BIN3,
    "\u2A65": MO.BIN3,
    "\u2A66": MO.REL,
    "\u2A67": MO.REL,
    "\u2A68": MO.REL,
    "\u2A69": MO.REL,
    "\u2A6A": MO.REL,
    "\u2A6B": MO.REL,
    "\u2A6C": MO.REL,
    "\u2A6D": MO.REL,
    "\u2A6E": MO.REL,
    "\u2A6F": MO.REL,
    "\u2A70": MO.REL,
    "\u2A71": MO.REL,
    "\u2A72": MO.REL,
    "\u2A73": MO.REL,
    "\u2A74": MO.REL,
    "\u2A75": MO.REL,
    "\u2A76": MO.REL,
    "\u2A77": MO.REL,
    "\u2A78": MO.REL,
    "\u2A79": MO.REL,
    "\u2A7A": MO.REL,
    "\u2A7B": MO.REL,
    "\u2A7C": MO.REL,
    "\u2A7D": MO.REL,
    "\u2A7D\u0338": MO.REL,
    "\u2A7E": MO.REL,
    "\u2A7E\u0338": MO.REL,
    "\u2A7F": MO.REL,
    "\u2A80": MO.REL,
    "\u2A81": MO.REL,
    "\u2A82": MO.REL,
    "\u2A83": MO.REL,
    "\u2A84": MO.REL,
    "\u2A85": MO.REL,
    "\u2A86": MO.REL,
    "\u2A87": MO.REL,
    "\u2A88": MO.REL,
    "\u2A89": MO.REL,
    "\u2A8A": MO.REL,
    "\u2A8B": MO.REL,
    "\u2A8C": MO.REL,
    "\u2A8D": MO.REL,
    "\u2A8E": MO.REL,
    "\u2A8F": MO.REL,
    "\u2A90": MO.REL,
    "\u2A91": MO.REL,
    "\u2A92": MO.REL,
    "\u2A93": MO.REL,
    "\u2A94": MO.REL,
    "\u2A95": MO.REL,
    "\u2A96": MO.REL,
    "\u2A97": MO.REL,
    "\u2A98": MO.REL,
    "\u2A99": MO.REL,
    "\u2A9A": MO.REL,
    "\u2A9B": MO.REL,
    "\u2A9C": MO.REL,
    "\u2A9D": MO.REL,
    "\u2A9E": MO.REL,
    "\u2A9F": MO.REL,
    "\u2AA0": MO.REL,
    "\u2AA1": MO.REL,
    "\u2AA2": MO.REL,
    "\u2AA3": MO.REL,
    "\u2AA4": MO.REL,
    "\u2AA5": MO.REL,
    "\u2AA6": MO.REL,
    "\u2AA7": MO.REL,
    "\u2AA8": MO.REL,
    "\u2AA9": MO.REL,
    "\u2AAA": MO.REL,
    "\u2AAB": MO.REL,
    "\u2AAC": MO.REL,
    "\u2AAD": MO.REL,
    "\u2AAE": MO.REL,
    "\u2AAF": MO.REL,
    "\u2AAF\u0338": MO.REL,
    "\u2AB0": MO.REL,
    "\u2AB0\u0338": MO.REL,
    "\u2AB1": MO.REL,
    "\u2AB2": MO.REL,
    "\u2AB3": MO.REL,
    "\u2AB4": MO.REL,
    "\u2AB5": MO.REL,
    "\u2AB6": MO.REL,
    "\u2AB7": MO.REL,
    "\u2AB8": MO.REL,
    "\u2AB9": MO.REL,
    "\u2ABA": MO.REL,
    "\u2ABB": MO.REL,
    "\u2ABC": MO.REL,
    "\u2ABD": MO.REL,
    "\u2ABE": MO.REL,
    "\u2ABF": MO.REL,
    "\u2AC0": MO.REL,
    "\u2AC1": MO.REL,
    "\u2AC2": MO.REL,
    "\u2AC3": MO.REL,
    "\u2AC4": MO.REL,
    "\u2AC5": MO.REL,
    "\u2AC6": MO.REL,
    "\u2AC7": MO.REL,
    "\u2AC8": MO.REL,
    "\u2AC9": MO.REL,
    "\u2ACA": MO.REL,
    "\u2ACB": MO.REL,
    "\u2ACC": MO.REL,
    "\u2ACD": MO.REL,
    "\u2ACE": MO.REL,
    "\u2ACF": MO.REL,
    "\u2AD0": MO.REL,
    "\u2AD1": MO.REL,
    "\u2AD2": MO.REL,
    "\u2AD3": MO.REL,
    "\u2AD4": MO.REL,
    "\u2AD5": MO.REL,
    "\u2AD6": MO.REL,
    "\u2AD7": MO.REL,
    "\u2AD8": MO.REL,
    "\u2AD9": MO.REL,
    "\u2ADA": MO.REL,
    "\u2ADB": MO.BIN4,
    "\u2ADD": MO.BIN3,
    "\u2ADD\u0338": MO.REL,
    "\u2ADE": MO.REL,
    "\u2ADF": MO.REL,
    "\u2AE0": MO.REL,
    "\u2AE1": MO.REL,
    "\u2AE2": MO.REL,
    "\u2AE3": MO.REL,
    "\u2AE4": MO.REL,
    "\u2AE5": MO.REL,
    "\u2AE6": MO.REL,
    "\u2AE7": MO.REL,
    "\u2AE8": MO.REL,
    "\u2AE9": MO.REL,
    "\u2AEA": MO.REL,
    "\u2AEB": MO.REL,
    "\u2AEE": MO.REL,
    "\u2AF2": MO.REL,
    "\u2AF3": MO.REL,
    "\u2AF4": MO.REL,
    "\u2AF5": MO.REL,
    "\u2AF6": MO.BIN4,
    "\u2AF7": MO.REL,
    "\u2AF8": MO.REL,
    "\u2AF9": MO.REL,
    "\u2AFA": MO.REL,
    "\u2AFB": MO.BIN4,
    "\u2AFD": MO.BIN4,
    "\u2AFE": MO.BIN3,
    "\u2B00": MO.REL,
    "\u2B01": MO.REL,
    "\u2B02": MO.REL,
    "\u2B03": MO.REL,
    "\u2B04": MO.WIDEREL,
    "\u2B05": MO.WIDEREL,
    "\u2B06": MO.RELSTRETCH,
    "\u2B07": MO.RELSTRETCH,
    "\u2B08": MO.REL,
    "\u2B09": MO.REL,
    "\u2B0A": MO.REL,
    "\u2B0B": MO.REL,
    "\u2B0C": MO.WIDEREL,
    "\u2B0D": MO.RELSTRETCH,
    "\u2B0E": MO.RELSTRETCH,
    "\u2B0F": MO.RELSTRETCH,
    "\u2B10": MO.RELSTRETCH,
    "\u2B11": MO.RELSTRETCH,
    "\u2B30": MO.WIDEREL,
    "\u2B31": MO.WIDEREL,
    "\u2B32": MO.RELSTRETCH,
    "\u2B33": MO.WIDEREL,
    "\u2B34": MO.WIDEREL,
    "\u2B35": MO.WIDEREL,
    "\u2B36": MO.WIDEREL,
    "\u2B37": MO.WIDEREL,
    "\u2B38": MO.WIDEREL,
    "\u2B39": MO.WIDEREL,
    "\u2B3A": MO.WIDEREL,
    "\u2B3B": MO.WIDEREL,
    "\u2B3C": MO.WIDEREL,
    "\u2B3D": MO.WIDEREL,
    "\u2B3E": MO.WIDEREL,
    "\u2B3F": MO.RELACCENT,
    "\u2B40": MO.WIDEREL,
    "\u2B41": MO.WIDEREL,
    "\u2B42": MO.WIDEREL,
    "\u2B43": MO.WIDEREL,
    "\u2B44": MO.WIDEREL,
    "\u2B45": MO.WIDEREL,
    "\u2B46": MO.WIDEREL,
    "\u2B47": MO.WIDEREL,
    "\u2B48": MO.WIDEREL,
    "\u2B49": MO.WIDEREL,
    "\u2B4A": MO.WIDEREL,
    "\u2B4B": MO.WIDEREL,
    "\u2B4C": MO.WIDEREL,
    "\u2B4D": MO.REL,
    "\u2B4E": MO.REL,
    "\u2B4F": MO.REL,
    "\u2B5A": MO.REL,
    "\u2B5B": MO.REL,
    "\u2B5C": MO.REL,
    "\u2B5D": MO.REL,
    "\u2B5E": MO.REL,
    "\u2B5F": MO.REL,
    "\u2B60": MO.WIDEREL,
    "\u2B61": MO.RELSTRETCH,
    "\u2B62": MO.WIDEREL,
    "\u2B63": MO.RELSTRETCH,
    "\u2B64": MO.WIDEREL,
    "\u2B65": MO.RELSTRETCH,
    "\u2B66": MO.REL,
    "\u2B67": MO.REL,
    "\u2B68": MO.REL,
    "\u2B69": MO.REL,
    "\u2B6A": MO.WIDEREL,
    "\u2B6B": MO.RELSTRETCH,
    "\u2B6C": MO.WIDEREL,
    "\u2B6D": MO.RELSTRETCH,
    "\u2B6E": MO.REL,
    "\u2B6F": MO.REL,
    "\u2B70": MO.WIDEREL,
    "\u2B71": MO.RELSTRETCH,
    "\u2B72": MO.WIDEREL,
    "\u2B73": MO.RELSTRETCH,
    "\u2B76": MO.REL,
    "\u2B77": MO.REL,
    "\u2B78": MO.REL,
    "\u2B79": MO.REL,
    "\u2B7A": MO.WIDEREL,
    "\u2B7B": MO.RELSTRETCH,
    "\u2B7C": MO.WIDEREL,
    "\u2B7D": MO.RELSTRETCH,
    "\u2B80": MO.WIDEREL,
    "\u2B81": MO.RELSTRETCH,
    "\u2B82": MO.WIDEREL,
    "\u2B83": MO.RELSTRETCH,
    "\u2B84": MO.WIDEREL,
    "\u2B85": MO.RELSTRETCH,
    "\u2B86": MO.WIDEREL,
    "\u2B87": MO.RELSTRETCH,
    "\u2B88": MO.RELACCENT,
    "\u2B89": MO.REL,
    "\u2B8A": MO.RELACCENT,
    "\u2B8B": MO.REL,
    "\u2B8C": MO.REL,
    "\u2B8D": MO.REL,
    "\u2B8E": MO.REL,
    "\u2B8F": MO.REL,
    "\u2B94": MO.REL,
    "\u2B95": MO.WIDEREL,
    "\u2BA0": MO.RELSTRETCH,
    "\u2BA1": MO.RELSTRETCH,
    "\u2BA2": MO.RELSTRETCH,
    "\u2BA3": MO.RELSTRETCH,
    "\u2BA4": MO.RELSTRETCH,
    "\u2BA5": MO.RELSTRETCH,
    "\u2BA6": MO.RELSTRETCH,
    "\u2BA7": MO.RELSTRETCH,
    "\u2BA8": MO.WIDEREL,
    "\u2BA9": MO.WIDEREL,
    "\u2BAA": MO.WIDEREL,
    "\u2BAB": MO.WIDEREL,
    "\u2BAC": MO.RELSTRETCH,
    "\u2BAD": MO.RELSTRETCH,
    "\u2BAE": MO.RELSTRETCH,
    "\u2BAF": MO.RELSTRETCH,
    "\u2BB0": MO.REL,
    "\u2BB1": MO.REL,
    "\u2BB2": MO.REL,
    "\u2BB3": MO.REL,
    "\u2BB4": MO.REL,
    "\u2BB5": MO.REL,
    "\u2BB6": MO.REL,
    "\u2BB7": MO.REL,
    "\u2BB8": MO.RELSTRETCH,
    "\u2BD1": MO.REL,
    "\u3ADC": MO.BIN3,
    "\uFE37": MO.WIDEACCENT,
    "\uFE38": MO.WIDEACCENT
  }
};

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mo.js
var MmlMo = class extends AbstractMmlTokenNode {
  constructor() {
    super(...arguments);
    this._texClass = null;
    this.lspace = 5 / 18;
    this.rspace = 5 / 18;
  }
  get texClass() {
    if (this._texClass === null) {
      return this.getOperatorDef(this.getText())[2];
    }
    return this._texClass;
  }
  set texClass(value) {
    this._texClass = value;
  }
  get kind() {
    return "mo";
  }
  get isEmbellished() {
    return true;
  }
  coreParent() {
    let embellished = null;
    let parent = this;
    const math = this.factory.getNodeClass("math");
    while (parent && parent.isEmbellished && parent.coreMO() === this && !(parent instanceof math)) {
      embellished = parent;
      parent = parent.parent;
    }
    return embellished || this;
  }
  coreText(parent) {
    if (!parent) {
      return "";
    }
    if (parent.isEmbellished) {
      return parent.coreMO().getText();
    }
    while (((parent.isKind("mrow") || parent.isKind("TeXAtom") || parent.isKind("mstyle") || parent.isKind("mphantom")) && parent.childNodes.length === 1 || parent.isKind("munderover")) && parent.childNodes[0]) {
      parent = parent.childNodes[0];
    }
    return parent.isToken ? parent.getText() : "";
  }
  hasSpacingAttributes() {
    return this.attributes.isSet("lspace") || this.attributes.isSet("rspace");
  }
  get isAccent() {
    let accent = false;
    const node = this.coreParent().parent;
    if (node) {
      const key = node.isKind("mover") ? node.childNodes[node.over].coreMO() ? "accent" : "" : node.isKind("munder") ? node.childNodes[node.under].coreMO() ? "accentunder" : "" : node.isKind("munderover") ? this === node.childNodes[node.over].coreMO() ? "accent" : this === node.childNodes[node.under].coreMO() ? "accentunder" : "" : "";
      if (key) {
        const value = node.attributes.getExplicit(key);
        accent = value !== void 0 ? accent : this.attributes.get("accent");
      }
    }
    return accent;
  }
  setTeXclass(prev) {
    const { form, fence } = this.attributes.getList("form", "fence");
    if (this.getProperty("texClass") === void 0 && this.hasSpacingAttributes()) {
      return null;
    }
    if (fence && this.texClass === TEXCLASS.REL) {
      if (form === "prefix") {
        this.texClass = TEXCLASS.OPEN;
      }
      if (form === "postfix") {
        this.texClass = TEXCLASS.CLOSE;
      }
    }
    return this.adjustTeXclass(prev);
  }
  adjustTeXclass(prev) {
    const texClass = this.texClass;
    let prevClass = this.prevClass;
    if (texClass === TEXCLASS.NONE) {
      return prev;
    }
    if (prev) {
      if (prev.getProperty("autoOP") && (texClass === TEXCLASS.BIN || texClass === TEXCLASS.REL)) {
        prevClass = prev.texClass = TEXCLASS.ORD;
      }
      prevClass = this.prevClass = prev.texClass || TEXCLASS.ORD;
      this.prevLevel = this.attributes.getInherited("scriptlevel");
    } else {
      prevClass = this.prevClass = TEXCLASS.NONE;
    }
    if (texClass === TEXCLASS.BIN && (prevClass === TEXCLASS.NONE || prevClass === TEXCLASS.BIN || prevClass === TEXCLASS.OP || prevClass === TEXCLASS.REL || prevClass === TEXCLASS.OPEN || prevClass === TEXCLASS.PUNCT)) {
      this.texClass = TEXCLASS.ORD;
    } else if (prevClass === TEXCLASS.BIN && (texClass === TEXCLASS.REL || texClass === TEXCLASS.CLOSE || texClass === TEXCLASS.PUNCT)) {
      prev.texClass = this.prevClass = TEXCLASS.ORD;
    } else if (texClass === TEXCLASS.BIN) {
      let child = null;
      let parent = this.parent;
      while (parent && parent.parent && parent.isEmbellished && (parent.childNodes.length === 1 || !parent.isKind("mrow") && parent.core() === child)) {
        child = parent;
        parent = parent.parent;
      }
      child = child || this;
      if (parent.childNodes[parent.childNodes.length - 1] === child) {
        this.texClass = TEXCLASS.ORD;
      }
    }
    return this;
  }
  setInheritedAttributes(attributes = {}, display = false, level = 0, prime = false) {
    super.setInheritedAttributes(attributes, display, level, prime);
    const mo = this.getText();
    this.checkOperatorTable(mo);
    this.checkPseudoScripts(mo);
    this.checkPrimes(mo);
    this.checkMathAccent(mo);
  }
  getOperatorDef(mo) {
    const [form1, form2, form3] = this.handleExplicitForm(this.getForms());
    this.attributes.setInherited("form", form1);
    const CLASS = this.constructor;
    const OPTABLE2 = CLASS.OPTABLE;
    const def = OPTABLE2[form1][mo] || OPTABLE2[form2][mo] || OPTABLE2[form3][mo];
    if (def) {
      return def;
    }
    this.setProperty("noDictDef", true);
    const limits = this.attributes.get("movablelimits");
    const isOP = !!mo.match(CLASS.opPattern);
    if ((isOP || limits) && this.getProperty("texClass") === void 0) {
      return OPDEF(1, 2, TEXCLASS.OP);
    }
    const range = getRange(mo);
    const [l, r] = CLASS.MMLSPACING[range[2]];
    return OPDEF(l, r, range[2]);
  }
  checkOperatorTable(mo) {
    const def = this.getOperatorDef(mo);
    if (this.getProperty("texClass") === void 0) {
      this.texClass = def[2];
    }
    for (const name of Object.keys(def[3] || {})) {
      this.attributes.setInherited(name, def[3][name]);
    }
    this.lspace = def[0] / 18;
    this.rspace = def[1] / 18;
  }
  getForms() {
    let core = null;
    let parent = this.parent;
    let Parent = this.Parent;
    while (Parent && Parent.isEmbellished) {
      core = parent;
      parent = Parent.parent;
      Parent = Parent.Parent;
    }
    core = core || this;
    if (parent && parent.isKind("mrow") && parent.nonSpaceLength() !== 1) {
      if (parent.firstNonSpace() === core) {
        return ["prefix", "infix", "postfix"];
      }
      if (parent.lastNonSpace() === core) {
        return ["postfix", "infix", "prefix"];
      }
    }
    return ["infix", "prefix", "postfix"];
  }
  handleExplicitForm(forms) {
    if (this.attributes.isSet("form")) {
      const form = this.attributes.get("form");
      forms = [form].concat(forms.filter((name) => name !== form));
    }
    return forms;
  }
  checkPseudoScripts(mo) {
    const PSEUDOSCRIPTS = this.constructor.pseudoScripts;
    if (!mo.match(PSEUDOSCRIPTS))
      return;
    const parent = this.coreParent().Parent;
    const isPseudo = !parent || !(parent.isKind("msubsup") && !parent.isKind("msub"));
    this.setProperty("pseudoscript", isPseudo);
    if (isPseudo) {
      this.attributes.setInherited("lspace", 0);
      this.attributes.setInherited("rspace", 0);
    }
  }
  checkPrimes(mo) {
    const PRIMES = this.constructor.primes;
    if (!mo.match(PRIMES))
      return;
    const REMAP = this.constructor.remapPrimes;
    const primes = unicodeString(unicodeChars(mo).map((c) => REMAP[c]));
    this.setProperty("primes", primes);
  }
  checkMathAccent(mo) {
    const parent = this.Parent;
    if (this.getProperty("mathaccent") !== void 0 || !parent || !parent.isKind("munderover")) {
      return;
    }
    const [base, under, over] = parent.childNodes;
    if (base.isEmbellished && base.coreMO() === this)
      return;
    const isUnder = !!(under && under.isEmbellished && under.coreMO() === this);
    const isOver = !!(over && over.isEmbellished && under.coreMO() === this);
    if (!isUnder && !isOver)
      return;
    if (this.isMathAccent(mo)) {
      this.setProperty("mathaccent", true);
    } else if (this.isMathAccentWithWidth(mo)) {
      this.setProperty("mathaccent", false);
    }
  }
  isMathAccent(mo = this.getText()) {
    const MATHACCENT = this.constructor.mathaccents;
    return !!mo.match(MATHACCENT);
  }
  isMathAccentWithWidth(mo = this.getText()) {
    const MATHACCENT = this.constructor.mathaccentsWithWidth;
    return !!mo.match(MATHACCENT);
  }
};
MmlMo.defaults = Object.assign(Object.assign({}, AbstractMmlTokenNode.defaults), { form: "infix", fence: false, separator: false, lspace: "thickmathspace", rspace: "thickmathspace", stretchy: false, symmetric: false, maxsize: "infinity", minsize: "0em", largeop: false, movablelimits: false, accent: false, linebreak: "auto", lineleading: "100%", linebreakstyle: "before", indentalign: "auto", indentshift: "0", indenttarget: "", indentalignfirst: "indentalign", indentshiftfirst: "indentshift", indentalignlast: "indentalign", indentshiftlast: "indentshift" });
MmlMo.MMLSPACING = MMLSPACING;
MmlMo.OPTABLE = OPTABLE;
MmlMo.pseudoScripts = new RegExp([
  "^[\"'*`",
  "\xAA",
  "\xB0",
  "\xB2-\xB4",
  "\xB9",
  "\xBA",
  "\u2018-\u201F",
  "\u2032-\u2037\u2057",
  "\u2070\u2071",
  "\u2074-\u207F",
  "\u2080-\u208E",
  "]+$"
].join(""));
MmlMo.primes = new RegExp([
  `^["'`,
  "\u2018-\u201F",
  "]+$"
].join(""));
MmlMo.opPattern = /^[a-zA-Z]{2,}$/;
MmlMo.remapPrimes = {
  34: 8243,
  39: 8242,
  8216: 8245,
  8217: 8242,
  8218: 8242,
  8219: 8245,
  8220: 8246,
  8221: 8243,
  8222: 8243,
  8223: 8246
};
MmlMo.mathaccents = new RegExp([
  "^[",
  "\xB4\u0301\u02CA",
  "`\u0300\u02CB",
  "\xA8\u0308",
  "~\u0303\u02DC",
  "\xAF\u0304\u02C9",
  "\u02D8\u0306",
  "\u02C7\u030C",
  "^\u0302\u02C6",
  "\u20D0\u20D1",
  "\u20D6\u20D7\u20E1",
  "\u02D9\u0307",
  "\u02DA\u030A",
  "\u20DB",
  "\u20DC",
  "]$"
].join(""));
MmlMo.mathaccentsWithWidth = new RegExp([
  "^[",
  "\u2190\u2192\u2194",
  "\u23DC\u23DD",
  "\u23DE\u23DF",
  "]$"
].join(""));

// node_modules/@mathjax/src/mjs/input/tex/NodeUtil.js
var NodeUtil = {
  attrs: /* @__PURE__ */ new Set([
    "autoOP",
    "fnOP",
    "movesupsub",
    "subsupOK",
    "texprimestyle",
    "useHeight",
    "variantForm",
    "withDelims",
    "mathaccent",
    "open",
    "close"
  ]),
  createEntity(code) {
    return String.fromCodePoint(parseInt(code, 16));
  },
  getChildren(node) {
    return node.childNodes;
  },
  getText(node) {
    return node.getText();
  },
  appendChildren(node, children) {
    for (const child of children) {
      node.appendChild(child);
    }
  },
  setAttribute(node, attribute, value) {
    node.attributes.set(attribute, value);
  },
  setProperty(node, property, value) {
    node.setProperty(property, value);
  },
  setProperties(node, properties) {
    for (const name of Object.keys(properties)) {
      const value = properties[name];
      if (name === "texClass") {
        node.texClass = value;
        node.setProperty(name, value);
      } else if (name === "movablelimits") {
        node.setProperty("movablelimits", value);
        if (node.isKind("mo") || node.isKind("mstyle")) {
          node.attributes.set("movablelimits", value);
        }
      } else if (name === "inferred") {
      } else if (NodeUtil.attrs.has(name)) {
        node.setProperty(name, value);
      } else {
        node.attributes.set(name, value);
      }
    }
  },
  getProperty(node, property) {
    return node.getProperty(property);
  },
  getAttribute(node, attr) {
    return node.attributes.get(attr);
  },
  removeAttribute(node, attr) {
    node.attributes.unset(attr);
  },
  removeProperties(node, ...properties) {
    node.removeProperty(...properties);
  },
  getChildAt(node, position) {
    return node.childNodes[position];
  },
  setChild(node, position, child) {
    const children = node.childNodes;
    children[position] = child;
    if (child) {
      child.parent = node;
    }
  },
  copyChildren(oldNode, newNode) {
    const children = oldNode.childNodes;
    for (let i = 0; i < children.length; i++) {
      this.setChild(newNode, i, children[i]);
    }
  },
  copyAttributes(oldNode, newNode) {
    newNode.attributes = oldNode.attributes;
    for (const [prop, value] of Object.entries(oldNode.getAllProperties())) {
      newNode.setProperty(prop, value);
    }
  },
  isType(node, kind) {
    return node.isKind(kind);
  },
  isEmbellished(node) {
    return node.isEmbellished;
  },
  getTexClass(node) {
    return node.texClass;
  },
  getCoreMO(node) {
    return node.coreMO();
  },
  isNode(item) {
    return item instanceof AbstractMmlNode || item instanceof AbstractMmlEmptyNode;
  },
  isInferred(node) {
    return node.isInferred;
  },
  getForm(node) {
    if (!node.isKind("mo")) {
      return null;
    }
    const mo = node;
    const forms = mo.getForms();
    for (const form of forms) {
      const symbol = this.getOp(mo, form);
      if (symbol) {
        return symbol;
      }
    }
    return null;
  },
  getOp(mo, form = "infix") {
    return MmlMo.OPTABLE[form][mo.getText()] || null;
  },
  getMoAttribute(mo, attr) {
    var _a, _b;
    if (!mo.attributes.isSet(attr)) {
      for (const form of ["infix", "postfix", "prefix"]) {
        const value = (_b = (_a = this.getOp(mo, form)) === null || _a === void 0 ? void 0 : _a[3]) === null || _b === void 0 ? void 0 : _b[attr];
        if (value !== void 0) {
          return value;
        }
      }
    }
    return mo.attributes.get(attr);
  }
};
var NodeUtil_default = NodeUtil;

// node_modules/@mathjax/src/mjs/input/tex/TexConstants.js
var TexConstant = {
  Variant: {
    NORMAL: "normal",
    BOLD: "bold",
    ITALIC: "italic",
    BOLDITALIC: "bold-italic",
    DOUBLESTRUCK: "double-struck",
    FRAKTUR: "fraktur",
    BOLDFRAKTUR: "bold-fraktur",
    SCRIPT: "script",
    BOLDSCRIPT: "bold-script",
    SANSSERIF: "sans-serif",
    BOLDSANSSERIF: "bold-sans-serif",
    SANSSERIFITALIC: "sans-serif-italic",
    SANSSERIFBOLDITALIC: "sans-serif-bold-italic",
    MONOSPACE: "monospace",
    INITIAL: "inital",
    TAILED: "tailed",
    LOOPED: "looped",
    STRETCHED: "stretched",
    CALLIGRAPHIC: "-tex-calligraphic",
    BOLDCALLIGRAPHIC: "-tex-bold-calligraphic",
    OLDSTYLE: "-tex-oldstyle",
    BOLDOLDSTYLE: "-tex-bold-oldstyle",
    MATHITALIC: "-tex-mathit"
  },
  Form: {
    PREFIX: "prefix",
    INFIX: "infix",
    POSTFIX: "postfix"
  },
  LineBreak: {
    AUTO: "auto",
    NEWLINE: "newline",
    NOBREAK: "nobreak",
    GOODBREAK: "goodbreak",
    BADBREAK: "badbreak"
  },
  LineBreakStyle: {
    BEFORE: "before",
    AFTER: "after",
    DUPLICATE: "duplicate",
    INFIXLINBREAKSTYLE: "infixlinebreakstyle"
  },
  IndentAlign: {
    LEFT: "left",
    CENTER: "center",
    RIGHT: "right",
    AUTO: "auto",
    ID: "id",
    INDENTALIGN: "indentalign"
  },
  IndentShift: {
    INDENTSHIFT: "indentshift"
  },
  LineThickness: {
    THIN: "thin",
    MEDIUM: "medium",
    THICK: "thick"
  },
  Notation: {
    LONGDIV: "longdiv",
    ACTUARIAL: "actuarial",
    PHASORANGLE: "phasorangle",
    RADICAL: "radical",
    BOX: "box",
    ROUNDEDBOX: "roundedbox",
    CIRCLE: "circle",
    LEFT: "left",
    RIGHT: "right",
    TOP: "top",
    BOTTOM: "bottom",
    UPDIAGONALSTRIKE: "updiagonalstrike",
    DOWNDIAGONALSTRIKE: "downdiagonalstrike",
    VERTICALSTRIKE: "verticalstrike",
    HORIZONTALSTRIKE: "horizontalstrike",
    NORTHEASTARROW: "northeastarrow",
    MADRUWB: "madruwb",
    UPDIAGONALARROW: "updiagonalarrow"
  },
  Align: {
    TOP: "top",
    BOTTOM: "bottom",
    CENTER: "center",
    BASELINE: "baseline",
    AXIS: "axis",
    LEFT: "left",
    RIGHT: "right"
  },
  Lines: {
    NONE: "none",
    SOLID: "solid",
    DASHED: "dashed"
  },
  Side: {
    LEFT: "left",
    RIGHT: "right",
    LEFTOVERLAP: "leftoverlap",
    RIGHTOVERLAP: "rightoverlap"
  },
  Width: {
    AUTO: "auto",
    FIT: "fit"
  },
  Actiontype: {
    TOGGLE: "toggle",
    STATUSLINE: "statusline",
    TOOLTIP: "tooltip",
    INPUT: "input"
  },
  Overflow: {
    LINBREAK: "linebreak",
    SCROLL: "scroll",
    ELIDE: "elide",
    TRUNCATE: "truncate",
    SCALE: "scale"
  },
  Unit: {
    EM: "em",
    EX: "ex",
    PX: "px",
    IN: "in",
    CM: "cm",
    MM: "mm",
    PT: "pt",
    PC: "pc"
  },
  Attr: {
    LATEX: "data-latex",
    LATEXITEM: "data-latex-item"
  }
};

// node_modules/@mathjax/src/mjs/input/tex/FilterUtil.js
function _copyExplicit(attrs, node1, node2) {
  const attr1 = node1.attributes;
  const attr2 = node2.attributes;
  attrs.forEach((x) => {
    const attr = attr2.getExplicit(x);
    if (attr != null) {
      attr1.set(x, attr);
    }
  });
}
function _compareExplicit(node1, node2) {
  const filter = (attr, space) => {
    const exp = attr.getExplicitNames();
    return exp.filter((x) => {
      return x !== space && (x !== "stretchy" || attr.getExplicit("stretchy")) && x !== "data-latex" && x !== "data-latex-item";
    });
  };
  const attr1 = node1.attributes;
  const attr2 = node2.attributes;
  const exp1 = filter(attr1, "lspace");
  const exp2 = filter(attr2, "rspace");
  if (exp1.length !== exp2.length) {
    return false;
  }
  for (const name of exp1) {
    if (attr1.getExplicit(name) !== attr2.getExplicit(name)) {
      return false;
    }
  }
  return true;
}
function _cleanSubSup(options2, low, up) {
  const remove = [];
  for (const mml of options2.getList("m" + low + up)) {
    const children = mml.childNodes;
    if (children[mml[low]] && children[mml[up]]) {
      continue;
    }
    const parent = mml.parent;
    const newNode = children[mml[low]] ? options2.nodeFactory.create("node", "m" + low, [
      children[mml.base],
      children[mml[low]]
    ]) : options2.nodeFactory.create("node", "m" + up, [
      children[mml.base],
      children[mml[up]]
    ]);
    NodeUtil_default.copyAttributes(mml, newNode);
    parent.replaceChild(newNode, mml);
    remove.push(mml);
  }
  options2.removeFromList("m" + low + up, remove);
}
function _moveLimits(options2, underover, subsup) {
  const remove = [];
  for (const mml of options2.getList(underover)) {
    if (mml.attributes.get("displaystyle")) {
      continue;
    }
    const base = mml.childNodes[mml.base];
    const mo = base.coreMO();
    if (base.getProperty("movablelimits") && !mo.attributes.hasExplicit("movablelimits")) {
      const node = options2.nodeFactory.create("node", subsup, mml.childNodes);
      NodeUtil_default.copyAttributes(mml, node);
      mml.parent.replaceChild(node, mml);
      remove.push(mml);
    }
  }
  options2.removeFromList(underover, remove);
}
var FilterUtil = {
  cleanStretchy(arg) {
    var _a;
    const options2 = arg.data;
    for (const mo of options2.getList("fixStretchy")) {
      if (NodeUtil_default.getProperty(mo, "fixStretchy")) {
        const symbol = NodeUtil_default.getForm(mo);
        if ((_a = symbol === null || symbol === void 0 ? void 0 : symbol[3]) === null || _a === void 0 ? void 0 : _a["stretchy"]) {
          NodeUtil_default.setAttribute(mo, "stretchy", false);
        }
        NodeUtil_default.removeProperties(mo, "fixStretchy");
      }
    }
  },
  cleanAttributes(arg) {
    const node = arg.data.root;
    node.walkTree((mml) => {
      const keep = new Set((mml.getProperty("keep-attrs") || "").split(/ /));
      const attribs = mml.attributes;
      attribs.unset(TexConstant.Attr.LATEXITEM);
      for (const key of attribs.getExplicitNames()) {
        if (!keep.has(key) && attribs.get(key) === attribs.getInherited(key)) {
          attribs.unset(key);
        }
      }
    });
  },
  combineRelations(arg) {
    const remove = [];
    for (const mo of arg.data.getList("mo")) {
      if (mo.getProperty("relationsCombined") || !mo.parent || mo.parent && !NodeUtil_default.isType(mo.parent, "mrow") || NodeUtil_default.getTexClass(mo) !== TEXCLASS.REL) {
        continue;
      }
      const mml = mo.parent;
      let m2;
      const children = mml.childNodes;
      const next = children.indexOf(mo) + 1;
      const variantForm = NodeUtil_default.getProperty(mo, "variantForm");
      while (next < children.length && (m2 = children[next]) && NodeUtil_default.isType(m2, "mo") && NodeUtil_default.getTexClass(m2) === TEXCLASS.REL) {
        if (variantForm === NodeUtil_default.getProperty(m2, "variantForm") && _compareExplicit(mo, m2)) {
          NodeUtil_default.appendChildren(mo, NodeUtil_default.getChildren(m2));
          _copyExplicit(["stretchy", "rspace"], mo, m2);
          for (const name of m2.getPropertyNames()) {
            mo.setProperty(name, m2.getProperty(name));
          }
          if (m2.attributes.get("data-latex")) {
            mo.attributes.set("data-latex", mo.attributes.get("data-latex") + m2.attributes.get("data-latex"));
          }
          children.splice(next, 1);
          remove.push(m2);
          m2.parent = null;
          m2.setProperty("relationsCombined", true);
          mo.setProperty("texClass", TEXCLASS.REL);
        } else {
          if (!mo.attributes.hasExplicit("rspace")) {
            NodeUtil_default.setAttribute(mo, "rspace", "0pt");
          }
          if (!m2.attributes.hasExplicit("lspace")) {
            NodeUtil_default.setAttribute(m2, "lspace", "0pt");
          }
          break;
        }
      }
      mo.attributes.setInherited("form", mo.getForms()[0]);
    }
    arg.data.removeFromList("mo", remove);
  },
  cleanSubSup(arg) {
    const options2 = arg.data;
    if (options2.error) {
      return;
    }
    _cleanSubSup(options2, "sub", "sup");
    _cleanSubSup(options2, "under", "over");
  },
  moveLimits(arg) {
    const options2 = arg.data;
    _moveLimits(options2, "munderover", "msubsup");
    _moveLimits(options2, "munder", "msub");
    _moveLimits(options2, "mover", "msup");
  },
  setInherited(arg) {
    arg.data.root.setInheritedAttributes({}, arg.math["display"], 0, false);
  },
  checkScriptlevel(arg) {
    const options2 = arg.data;
    const remove = [];
    for (const mml of options2.getList("mstyle")) {
      if (mml.childNodes[0].childNodes.length !== 1) {
        continue;
      }
      const attributes = mml.attributes;
      for (const key of ["displaystyle", "scriptlevel"]) {
        if (attributes.getExplicit(key) === attributes.getInherited(key)) {
          attributes.unset(key);
        }
      }
      const names = attributes.getExplicitNames();
      if (names.filter((key) => key.substring(0, 10) !== "data-latex").length === 0) {
        const child = mml.childNodes[0].childNodes[0];
        names.forEach((key) => child.attributes.set(key, attributes.get(key)));
        mml.parent.replaceChild(child, mml);
        remove.push(mml);
      }
    }
    options2.removeFromList("mstyle", remove);
  }
};
var FilterUtil_default = FilterUtil;

// node_modules/@mathjax/src/mjs/input/tex/HandlerTypes.js
var ConfigurationType;
(function(ConfigurationType2) {
  ConfigurationType2["HANDLER"] = "handler";
  ConfigurationType2["FALLBACK"] = "fallback";
  ConfigurationType2["ITEMS"] = "items";
  ConfigurationType2["TAGS"] = "tags";
  ConfigurationType2["OPTIONS"] = "options";
  ConfigurationType2["NODES"] = "nodes";
  ConfigurationType2["PREPROCESSORS"] = "preprocessors";
  ConfigurationType2["POSTPROCESSORS"] = "postprocessors";
  ConfigurationType2["INIT"] = "init";
  ConfigurationType2["CONFIG"] = "config";
  ConfigurationType2["PRIORITY"] = "priority";
  ConfigurationType2["PARSER"] = "parser";
})(ConfigurationType || (ConfigurationType = {}));
var HandlerType;
(function(HandlerType2) {
  HandlerType2["DELIMITER"] = "delimiter";
  HandlerType2["MACRO"] = "macro";
  HandlerType2["CHARACTER"] = "character";
  HandlerType2["ENVIRONMENT"] = "environment";
})(HandlerType || (HandlerType = {}));

// node_modules/@mathjax/src/mjs/input/tex/UnitUtil.js
var UnitMap = class {
  constructor(map) {
    this.num = "([-+]?([.,]\\d+|\\d+([.,]\\d*)?))";
    this.unit = "";
    this.dimenEnd = /./;
    this.dimenRest = /./;
    this.map = new Map(map);
    this.updateDimen();
  }
  updateDimen() {
    this.unit = `(${Array.from(this.map.keys()).join("|")})`;
    this.dimenEnd = RegExp("^\\s*" + this.num + "\\s*" + this.unit + "\\s*$");
    this.dimenRest = RegExp("^\\s*" + this.num + "\\s*" + this.unit + " ?");
  }
  set(name, ems) {
    this.map.set(name, ems);
    this.updateDimen();
    return this;
  }
  get(name) {
    return this.map.get(name) || this.map.get("pt");
  }
  delete(name) {
    if (this.map.delete(name)) {
      this.updateDimen();
      return true;
    }
    return false;
  }
};
var emPerInch = 7.2;
var pxPerInch = 72;
function muReplace([value, unit, length]) {
  if (unit !== "mu") {
    return [value, unit, length];
  }
  const em2 = UnitUtil.em(UnitUtil.UNIT_CASES.get(unit) * parseFloat(value));
  return [em2.slice(0, -2), "em", length];
}
var UnitUtil = {
  UNIT_CASES: new UnitMap([
    ["em", 1],
    ["ex", 0.43],
    ["pt", 1 / 10],
    ["pc", 1.2],
    ["px", emPerInch / pxPerInch],
    ["in", emPerInch],
    ["cm", emPerInch / 2.54],
    ["mm", emPerInch / 25.4],
    ["mu", 1 / 18]
  ]),
  matchDimen(dim, rest = false) {
    const match = dim.match(rest ? UnitUtil.UNIT_CASES.dimenRest : UnitUtil.UNIT_CASES.dimenEnd);
    return match ? muReplace([match[1].replace(/,/, "."), match[4], match[0].length]) : [null, null, 0];
  },
  dimen2em(dim) {
    const [value, unit] = UnitUtil.matchDimen(dim);
    const m = parseFloat(value || "1");
    const factor = UnitUtil.UNIT_CASES.get(unit);
    return factor * m;
  },
  em(m) {
    if (Math.abs(m) < 6e-4) {
      return "0em";
    }
    return m.toFixed(3).replace(/\.?0+$/, "") + "em";
  },
  trimSpaces(text) {
    if (typeof text !== "string") {
      return text;
    }
    let TEXT = text.trim();
    if (TEXT.match(/\\$/) && text.match(/ $/)) {
      TEXT += " ";
    }
    return TEXT;
  }
};

// node_modules/@mathjax/src/mjs/input/tex/Stack.js
var Stack = class {
  constructor(_factory, _env, inner) {
    this._factory = _factory;
    this._env = _env;
    this.global = {};
    this.stack = [];
    this.global = { isInner: inner };
    this.stack = [this._factory.create("start", this.global)];
    if (_env) {
      this.stack[0].env = _env;
    }
    this.env = this.stack[0].env;
  }
  set env(env) {
    this._env = env;
  }
  get env() {
    return this._env;
  }
  Push(...args) {
    for (const node of args) {
      if (!node) {
        continue;
      }
      const item = NodeUtil_default.isNode(node) ? this._factory.create("mml", node) : node;
      item.global = this.global;
      const [top, success] = this.stack.length ? this.Top().checkItem(item) : [null, true];
      if (!success) {
        continue;
      }
      if (top) {
        this.Pop();
        this.Push(...top);
        continue;
      }
      if (!item.isKind("null")) {
        this.stack.push(item);
      }
      if (item.env) {
        if (item.copyEnv) {
          Object.assign(item.env, this.env);
        }
        this.env = item.env;
      } else {
        item.env = this.env;
      }
    }
  }
  Pop() {
    const item = this.stack.pop();
    if (!item.isOpen) {
      delete item.env;
    }
    this.env = this.stack.length ? this.Top().env : {};
    return item;
  }
  Top(n = 1) {
    return this.stack.length < n ? null : this.stack[this.stack.length - n];
  }
  Prev(noPop) {
    const top = this.Top();
    return noPop ? top.First : top.Pop();
  }
  get height() {
    return this.stack.length;
  }
  toString() {
    return "stack[\n  " + this.stack.join("\n  ") + "\n]";
  }
};

// node_modules/@mathjax/src/mjs/input/tex/TexError.js
var TexError = class _TexError {
  static processString(str, args) {
    const parts = str.split(_TexError.pattern);
    for (let i = 1, m = parts.length; i < m; i += 2) {
      let c = parts[i].charAt(0);
      if (c >= "0" && c <= "9") {
        parts[i] = args[parseInt(parts[i], 10) - 1];
        if (typeof parts[i] === "number") {
          parts[i] = parts[i].toString();
        }
      } else if (c === "{") {
        c = parts[i].substring(1);
        if (c >= "0" && c <= "9") {
          parts[i] = args[parseInt(parts[i].substring(1, parts[i].length - 1), 10) - 1];
          if (typeof parts[i] === "number") {
            parts[i] = parts[i].toString();
          }
        } else {
          const match = parts[i].match(/^\{([a-z]+):%(\d+)\|(.*)\}$/);
          if (match) {
            parts[i] = "%" + parts[i];
          }
        }
      }
    }
    return parts.join("");
  }
  constructor(id, message, ...rest) {
    this.id = id;
    this.message = _TexError.processString(message, rest);
  }
};
TexError.pattern = /%(\d+|\{\d+\}|\{[a-z]+:%\d+(?:\|(?:%\{\d+\}|%.|[^}])*)+\}|.)/g;
var TexError_default = TexError;

// node_modules/@mathjax/src/mjs/input/tex/StackItem.js
var MmlStack = class {
  constructor(_nodes) {
    this._nodes = _nodes;
    this.startStr = "";
    this.startI = 0;
    this.stopI = 0;
  }
  get nodes() {
    return this._nodes;
  }
  Push(...nodes) {
    this._nodes.push(...nodes);
  }
  Pop() {
    return this._nodes.pop();
  }
  get First() {
    return this._nodes[this.Size() - 1];
  }
  set First(node) {
    this._nodes[this.Size() - 1] = node;
  }
  get Last() {
    return this._nodes[0];
  }
  set Last(node) {
    this._nodes[0] = node;
  }
  Peek(n) {
    if (n == null) {
      n = 1;
    }
    return this._nodes.slice(this.Size() - n);
  }
  Size() {
    return this._nodes.length;
  }
  Clear() {
    this._nodes = [];
  }
  toMml(inferred = true, forceRow) {
    if (this._nodes.length === 1 && !forceRow) {
      return this.First;
    }
    return this.create("node", inferred ? "inferredMrow" : "mrow", this._nodes, {});
  }
  create(kind, ...rest) {
    return this.factory.configuration.nodeFactory.create(kind, ...rest);
  }
};
var BaseItem = class _BaseItem extends MmlStack {
  constructor(factory, ...nodes) {
    super(nodes);
    this.factory = factory;
    this.global = {};
    this._properties = {};
    if (this.isOpen) {
      this._env = {};
    }
  }
  get kind() {
    return "base";
  }
  get env() {
    return this._env;
  }
  set env(value) {
    this._env = value;
  }
  get copyEnv() {
    return true;
  }
  getProperty(key) {
    return this._properties[key];
  }
  setProperty(key, value) {
    this._properties[key] = value;
    return this;
  }
  get isOpen() {
    return false;
  }
  get isClose() {
    return false;
  }
  get isFinal() {
    return false;
  }
  isKind(kind) {
    return kind === this.kind;
  }
  checkItem(item) {
    if (item.isKind("over") && this.isOpen) {
      item.setProperty("num", this.toMml(false));
      this.Clear();
    }
    if (item.isKind("cell") && this.isOpen) {
      if (item.getProperty("linebreak")) {
        return _BaseItem.fail;
      }
      throw new TexError_default("Misplaced", "Misplaced %1", item.getName());
    }
    if (item.isClose && this.getErrors(item.kind)) {
      const [id, message] = this.getErrors(item.kind);
      throw new TexError_default(id, message, item.getName());
    }
    if (!item.isFinal) {
      return _BaseItem.success;
    }
    this.Push(item.First);
    return _BaseItem.fail;
  }
  clearEnv() {
    for (const id of Object.keys(this.env)) {
      delete this.env[id];
    }
  }
  setProperties(def) {
    Object.assign(this._properties, def);
    return this;
  }
  getName() {
    return this.getProperty("name");
  }
  toString() {
    return this.kind + "[" + this.nodes.join("; ") + "]";
  }
  getErrors(kind) {
    const CLASS = this.constructor;
    return CLASS.errors[kind] || _BaseItem.errors[kind];
  }
  addLatexItem(node, prefix = "") {
    const str = this.startStr.slice(this.startI, this.stopI);
    if (str) {
      const tex2 = prefix ? prefix + str : str;
      node.attributes.set(TexConstant.Attr.LATEXITEM, tex2);
      if (tex2 !== "}") {
        node.attributes.set(TexConstant.Attr.LATEX, tex2);
      }
    }
  }
};
BaseItem.fail = [null, false];
BaseItem.success = [null, true];
BaseItem.errors = {
  end: ["MissingBeginExtraEnd", "Missing \\begin{%1} or extra \\end{%1}"],
  close: ["ExtraCloseMissingOpen", "Extra close brace or missing open brace"],
  right: ["MissingLeftExtraRight", "Missing \\left or extra \\right"],
  middle: ["ExtraMiddle", "Extra \\middle"]
};

// node_modules/@mathjax/src/mjs/input/tex/TexParser.js
var TexParser = class _TexParser {
  constructor(_string, env, configuration) {
    this._string = _string;
    this.configuration = configuration;
    this.macroCount = 0;
    this.i = 0;
    this.currentCS = "";
    this.saveI = 0;
    const inner = Object.hasOwn(env, "isInner");
    const isInner = env["isInner"];
    delete env["isInner"];
    let ENV;
    if (env) {
      ENV = {};
      for (const id of Object.keys(env)) {
        ENV[id] = env[id];
      }
    }
    this.configuration.pushParser(this);
    this.stack = new Stack(this.itemFactory, ENV, inner ? isInner : true);
    this.Parse();
    this.Push(this.itemFactory.create("stop"));
    this.stack.env = ENV;
  }
  get options() {
    return this.configuration.options;
  }
  get itemFactory() {
    return this.configuration.itemFactory;
  }
  get tags() {
    return this.configuration.tags;
  }
  set string(str) {
    this._string = str;
  }
  get string() {
    return this._string;
  }
  parse(kind, input) {
    const i = this.saveI;
    this.saveI = this.i - (kind === "character" && input[1] !== "&" ? input[1].length : 0);
    const result = this.configuration.handlers.get(kind).parse(input);
    if (kind !== "macro") {
      this.updateResult(input[1], i);
    }
    this.saveI = i;
    return result;
  }
  lookup(kind, token) {
    return this.configuration.handlers.get(kind).lookup(token);
  }
  contains(kind, token) {
    return this.configuration.handlers.get(kind).contains(token);
  }
  toString() {
    let str = "";
    for (const config of Array.from(this.configuration.handlers.keys())) {
      str += config + ": " + this.configuration.handlers.get(config) + "\n";
    }
    return str;
  }
  Parse() {
    let c;
    while (this.i < this.string.length) {
      c = this.getCodePoint();
      this.i += c.length;
      this.parse(HandlerType.CHARACTER, [this, c]);
    }
  }
  Push(arg) {
    if (arg instanceof BaseItem) {
      arg.startI = this.saveI;
      arg.stopI = this.i;
      arg.startStr = this.string;
    }
    if (arg instanceof AbstractMmlNode && arg.isInferred) {
      this.PushAll(arg.childNodes);
    } else {
      this.stack.Push(arg);
    }
  }
  PushAll(args) {
    for (const arg of args) {
      this.stack.Push(arg);
    }
  }
  mml() {
    this.configuration.popParser();
    if (!this.stack.Top().isKind("mml")) {
      return null;
    }
    const node = this.stack.Top().First;
    const latex = this.trimTex(this.string);
    if (latex) {
      node.attributes.set(TexConstant.Attr.LATEX, latex);
    }
    return node;
  }
  convertDelimiter(c) {
    var _a;
    const token = this.lookup(HandlerType.DELIMITER, c);
    return (_a = token === null || token === void 0 ? void 0 : token.char) !== null && _a !== void 0 ? _a : null;
  }
  getCodePoint() {
    const code = this.string.codePointAt(this.i);
    return code === void 0 ? "" : String.fromCodePoint(code);
  }
  nextIsSpace() {
    return !!this.string.charAt(this.i).match(/\s/);
  }
  GetNext() {
    while (this.nextIsSpace()) {
      this.i++;
    }
    return this.getCodePoint();
  }
  GetCS() {
    const CS = this.string.slice(this.i).match(/^(([a-z]+) ?|[\uD800-\uDBFF].|.)/i);
    if (CS) {
      this.i += CS[0].length;
      return CS[2] || CS[1];
    } else {
      this.i++;
      return " ";
    }
  }
  GetArgument(_name, noneOK = false) {
    switch (this.GetNext()) {
      case "":
        if (!noneOK) {
          throw new TexError_default("MissingArgFor", "Missing argument for %1", this.currentCS);
        }
        return null;
      case "}":
        if (!noneOK) {
          throw new TexError_default("ExtraCloseMissingOpen", "Extra close brace or missing open brace");
        }
        return null;
      case "\\":
        this.i++;
        return "\\" + this.GetCS();
      case "{": {
        const j = ++this.i;
        let parens = 1;
        while (this.i < this.string.length) {
          switch (this.string.charAt(this.i++)) {
            case "\\":
              this.i++;
              break;
            case "{":
              parens++;
              break;
            case "}":
              if (--parens === 0) {
                return this.string.slice(j, this.i - 1);
              }
              break;
          }
        }
        throw new TexError_default("MissingCloseBrace", "Missing close brace");
      }
    }
    const c = this.getCodePoint();
    this.i += c.length;
    return c;
  }
  GetBrackets(_name, def, matchBrackets = false) {
    if (this.GetNext() !== "[") {
      return def;
    }
    const j = ++this.i;
    let braces = 0;
    let brackets = 0;
    while (this.i < this.string.length) {
      switch (this.string.charAt(this.i++)) {
        case "{":
          braces++;
          break;
        case "\\":
          this.i++;
          break;
        case "}":
          if (braces-- <= 0) {
            throw new TexError_default("ExtraCloseLooking", "Extra close brace while looking for %1", "']'");
          }
          break;
        case "[":
          if (braces === 0)
            brackets++;
          break;
        case "]":
          if (braces === 0) {
            if (!matchBrackets || brackets === 0) {
              return this.string.slice(j, this.i - 1);
            }
            brackets--;
          }
          break;
      }
    }
    throw new TexError_default("MissingCloseBracket", "Could not find closing ']' for argument to %1", this.currentCS);
  }
  GetDelimiter(name, braceOK = false) {
    let c = this.GetNext();
    this.i += c.length;
    if (this.i <= this.string.length) {
      if (c === "\\") {
        c += this.GetCS();
      } else if (c === "{" && braceOK) {
        this.i--;
        c = this.GetArgument(name).trim();
      }
      if (this.contains(HandlerType.DELIMITER, c)) {
        return this.convertDelimiter(c);
      }
    }
    throw new TexError_default("MissingOrUnrecognizedDelim", "Missing or unrecognized delimiter for %1", this.currentCS);
  }
  GetDimen(name) {
    if (this.GetNext() === "{") {
      const dimen = this.GetArgument(name);
      const [value, unit] = UnitUtil.matchDimen(dimen);
      if (value) {
        return value + unit;
      }
    } else {
      const dimen = this.string.slice(this.i);
      const [value, unit, length] = UnitUtil.matchDimen(dimen, true);
      if (value) {
        this.i += length;
        return value + unit;
      }
    }
    throw new TexError_default("MissingDimOrUnits", "Missing dimension or its units for %1", this.currentCS);
  }
  GetUpTo(_name, token) {
    while (this.nextIsSpace()) {
      this.i++;
    }
    const j = this.i;
    let braces = 0;
    while (this.i < this.string.length) {
      const k = this.i;
      let c = this.GetNext();
      this.i += c.length;
      switch (c) {
        case "\\":
          c += this.GetCS();
          break;
        case "{":
          braces++;
          break;
        case "}":
          if (braces === 0) {
            throw new TexError_default("ExtraCloseLooking", "Extra close brace while looking for %1", token);
          }
          braces--;
          break;
      }
      if (braces === 0 && c === token) {
        return this.string.slice(j, k);
      }
    }
    throw new TexError_default("TokenNotFoundForCommand", "Could not find %1 for %2", token, this.currentCS);
  }
  ParseArg(name) {
    return new _TexParser(this.GetArgument(name), this.stack.env, this.configuration).mml();
  }
  ParseUpTo(name, token) {
    return new _TexParser(this.GetUpTo(name, token), this.stack.env, this.configuration).mml();
  }
  GetDelimiterArg(name) {
    const c = UnitUtil.trimSpaces(this.GetArgument(name));
    if (c === "") {
      return null;
    }
    if (this.contains(HandlerType.DELIMITER, c)) {
      return c;
    }
    throw new TexError_default("MissingOrUnrecognizedDelim", "Missing or unrecognized delimiter for %1", this.currentCS);
  }
  GetStar() {
    const star = this.GetNext() === "*";
    if (star) {
      this.i++;
    }
    return star;
  }
  create(kind, ...rest) {
    const node = this.configuration.nodeFactory.create(kind, ...rest);
    if (node.isToken && node.attributes.hasExplicit("mathvariant")) {
      if (node.attributes.get("mathvariant").charAt(0) === "-") {
        node.setProperty("ignore-variant", true);
      }
    }
    return node;
  }
  trimTex(tex2) {
    return tex2.trim() + (tex2.match(/(?:^|[^\\])(?:\\\\)*\\\s+$/) ? " " : "");
  }
  updateResult(input, old) {
    const node = this.stack.Prev(true);
    if (!node) {
      return;
    }
    const LATEX = TexConstant.Attr.LATEX;
    const latex = node.attributes.get(LATEX);
    const existing = node.attributes.get(TexConstant.Attr.LATEXITEM);
    if (existing !== void 0) {
      if (!latex) {
        if (input === "}" || existing === "}") {
          this.composeBraces(node);
        } else {
          node.attributes.set(LATEX, existing);
        }
      }
      return;
    }
    old = old < this.saveI ? this.saveI : old;
    const str = this.trimTex(old !== this.i ? this.string.slice(old, this.i) : input);
    if (!str || str === latex || input === "\\" && str === "\\") {
      return;
    }
    if (str === "_" || str === "^") {
      node.setProperty("sub-sup", str);
    } else {
      switch (node.getProperty("sub-sup")) {
        case "^":
          if (node.childNodes[2]) {
            if (str === "}") {
              this.composeBraces(node.childNodes[2]);
            } else if (!node.childNodes[2].attributes.hasExplicit(LATEX)) {
              node.childNodes[2].attributes.set(LATEX, str);
            }
          }
          if (node.childNodes[1]) {
            const sub = node.childNodes[1].attributes.get(LATEX);
            this.composeLatex(node, `_${sub}^`, 0, 2);
          } else {
            this.composeLatex(node, "^", 0, 2);
          }
          return;
        case "_":
          if (node.childNodes[1]) {
            if (str === "}") {
              this.composeBraces(node.childNodes[1]);
            } else if (!node.childNodes[1].attributes.hasExplicit(LATEX)) {
              node.childNodes[1].attributes.set(LATEX, str);
            }
          }
          if (node.childNodes[2]) {
            const sup = node.childNodes[2].attributes.get(LATEX);
            this.composeLatex(node, `^${sup}_`, 0, 1);
          } else {
            this.composeLatex(node, "_", 0, 1);
          }
          return;
      }
      if (str === "}") {
        this.composeBraces(node);
        return;
      }
    }
    node.attributes.set(LATEX, str);
  }
  composeLatex(node, comp, pos1, pos2) {
    if (!node.childNodes[pos1] || !node.childNodes[pos2])
      return;
    const LATEX = TexConstant.Attr.LATEX;
    const expr = (node.childNodes[pos1].attributes.get(LATEX) || "") + comp + node.childNodes[pos2].attributes.get(LATEX);
    node.attributes.set(LATEX, expr);
  }
  composeBraces(atom) {
    const str = this.composeBracedContent(atom);
    atom.attributes.set(TexConstant.Attr.LATEX, `{${str}}`);
  }
  composeBracedContent(atom) {
    var _a, _b;
    const children = ((_a = atom.childNodes[0]) === null || _a === void 0 ? void 0 : _a.childNodes) || [];
    let expr = "";
    for (const child of children) {
      const att = ((_b = child === null || child === void 0 ? void 0 : child.attributes) === null || _b === void 0 ? void 0 : _b.get(TexConstant.Attr.LATEX)) || "";
      if (!att)
        continue;
      expr += expr && expr.match(/[a-zA-Z]$/) && att.match(/^[a-zA-Z]/) ? " " + att : att;
    }
    return expr;
  }
};

// node_modules/@mathjax/src/mjs/core/Tree/Factory.js
var AbstractFactory = class {
  constructor(nodes = null) {
    this.defaultKind = "unknown";
    this.nodeMap = /* @__PURE__ */ new Map();
    this.node = {};
    if (nodes === null) {
      nodes = this.constructor.defaultNodes;
    }
    for (const kind of Object.keys(nodes)) {
      this.setNodeClass(kind, nodes[kind]);
    }
  }
  create(kind, ...args) {
    return (this.node[kind] || this.node[this.defaultKind])(...args);
  }
  setNodeClass(kind, nodeClass) {
    this.nodeMap.set(kind, nodeClass);
    const KIND = this.nodeMap.get(kind);
    this.node[kind] = (...args) => {
      return new KIND(this, ...args);
    };
  }
  getNodeClass(kind) {
    return this.nodeMap.get(kind);
  }
  deleteNodeClass(kind) {
    this.nodeMap.delete(kind);
    delete this.node[kind];
  }
  nodeIsKind(node, kind) {
    return node instanceof this.getNodeClass(kind);
  }
  getKinds() {
    return Array.from(this.nodeMap.keys());
  }
};
AbstractFactory.defaultNodes = {};

// node_modules/@mathjax/src/mjs/input/tex/StackItemFactory.js
var DummyItem = class extends BaseItem {
};
var StackItemFactory = class extends AbstractFactory {
  constructor() {
    super(...arguments);
    this.defaultKind = "dummy";
    this.configuration = null;
  }
};
StackItemFactory.DefaultStackItems = {
  [DummyItem.prototype.kind]: DummyItem
};
var StackItemFactory_default = StackItemFactory;

// node_modules/@mathjax/src/mjs/input/tex/NodeFactory.js
var NodeFactory = class _NodeFactory {
  constructor() {
    this.mmlFactory = null;
    this.factory = {
      node: _NodeFactory.createNode,
      token: _NodeFactory.createToken,
      text: _NodeFactory.createText,
      error: _NodeFactory.createError
    };
  }
  static createNode(factory, kind, children = [], def = {}, text) {
    const node = factory.mmlFactory.create(kind);
    node.setChildren(children);
    if (text) {
      node.appendChild(text);
    }
    NodeUtil_default.setProperties(node, def);
    return node;
  }
  static createToken(factory, kind, def = {}, text = "") {
    const textNode = factory.create("text", text);
    return factory.create("node", kind, [], def, textNode);
  }
  static createText(factory, text) {
    if (text == null) {
      return null;
    }
    return factory.mmlFactory.create("text").setText(text);
  }
  static createError(factory, message) {
    const text = factory.create("text", message);
    const mtext = factory.create("node", "mtext", [], {}, text);
    const error = factory.create("node", "merror", [mtext], {
      "data-mjx-error": message
    });
    return error;
  }
  setMmlFactory(mmlFactory) {
    this.mmlFactory = mmlFactory;
  }
  set(kind, func) {
    this.factory[kind] = func;
  }
  setCreators(maps3) {
    for (const kind in maps3) {
      this.set(kind, maps3[kind]);
    }
  }
  create(kind, ...rest) {
    const func = this.factory[kind] || this.factory["node"];
    const node = func(this, rest[0], ...rest.slice(1));
    if (kind === "node") {
      this.configuration.addNode(rest[0], node);
    }
    return node;
  }
  get(kind) {
    return this.factory[kind];
  }
};

// node_modules/@mathjax/src/mjs/util/AsyncLoad.js
function asyncLoad(name) {
  if (!mathjax.asyncLoad) {
    return Promise.reject(`Can't load '${name}': No mathjax.asyncLoad method specified`);
  }
  return new Promise((ok, fail) => {
    const result = mathjax.asyncLoad(name);
    if (result instanceof Promise) {
      result.then((value) => ok(value)).catch((err) => fail(err));
    } else {
      ok(result);
    }
  });
}

// node_modules/@mathjax/src/mjs/util/Entities.js
var options = {
  loadMissingEntities: true
};
var entities = {
  ApplyFunction: "\u2061",
  Backslash: "\u2216",
  Because: "\u2235",
  Breve: "\u02D8",
  Cap: "\u22D2",
  CenterDot: "\xB7",
  CircleDot: "\u2299",
  CircleMinus: "\u2296",
  CirclePlus: "\u2295",
  CircleTimes: "\u2297",
  Congruent: "\u2261",
  ContourIntegral: "\u222E",
  Coproduct: "\u2210",
  Cross: "\u2A2F",
  Cup: "\u22D3",
  CupCap: "\u224D",
  Dagger: "\u2021",
  Del: "\u2207",
  Delta: "\u0394",
  Diamond: "\u22C4",
  DifferentialD: "\u2146",
  DotEqual: "\u2250",
  DoubleDot: "\xA8",
  DoubleRightTee: "\u22A8",
  DoubleVerticalBar: "\u2225",
  DownArrow: "\u2193",
  DownLeftVector: "\u21BD",
  DownRightVector: "\u21C1",
  DownTee: "\u22A4",
  Downarrow: "\u21D3",
  Element: "\u2208",
  EqualTilde: "\u2242",
  Equilibrium: "\u21CC",
  Exists: "\u2203",
  ExponentialE: "\u2147",
  FilledVerySmallSquare: "\u25AA",
  ForAll: "\u2200",
  Gamma: "\u0393",
  Gg: "\u22D9",
  GreaterEqual: "\u2265",
  GreaterEqualLess: "\u22DB",
  GreaterFullEqual: "\u2267",
  GreaterLess: "\u2277",
  GreaterSlantEqual: "\u2A7E",
  GreaterTilde: "\u2273",
  Hacek: "\u02C7",
  Hat: "^",
  HumpDownHump: "\u224E",
  HumpEqual: "\u224F",
  Im: "\u2111",
  ImaginaryI: "\u2148",
  Integral: "\u222B",
  Intersection: "\u22C2",
  InvisibleComma: "\u2063",
  InvisibleTimes: "\u2062",
  Lambda: "\u039B",
  Larr: "\u219E",
  LeftAngleBracket: "\u27E8",
  LeftArrow: "\u2190",
  LeftArrowRightArrow: "\u21C6",
  LeftCeiling: "\u2308",
  LeftDownVector: "\u21C3",
  LeftFloor: "\u230A",
  LeftRightArrow: "\u2194",
  LeftTee: "\u22A3",
  LeftTriangle: "\u22B2",
  LeftTriangleEqual: "\u22B4",
  LeftUpVector: "\u21BF",
  LeftVector: "\u21BC",
  Leftarrow: "\u21D0",
  Leftrightarrow: "\u21D4",
  LessEqualGreater: "\u22DA",
  LessFullEqual: "\u2266",
  LessGreater: "\u2276",
  LessSlantEqual: "\u2A7D",
  LessTilde: "\u2272",
  Ll: "\u22D8",
  Lleftarrow: "\u21DA",
  LongLeftArrow: "\u27F5",
  LongLeftRightArrow: "\u27F7",
  LongRightArrow: "\u27F6",
  Longleftarrow: "\u27F8",
  Longleftrightarrow: "\u27FA",
  Longrightarrow: "\u27F9",
  Lsh: "\u21B0",
  MinusPlus: "\u2213",
  NestedGreaterGreater: "\u226B",
  NestedLessLess: "\u226A",
  NotDoubleVerticalBar: "\u2226",
  NotElement: "\u2209",
  NotEqual: "\u2260",
  NotExists: "\u2204",
  NotGreater: "\u226F",
  NotGreaterEqual: "\u2271",
  NotLeftTriangle: "\u22EA",
  NotLeftTriangleEqual: "\u22EC",
  NotLess: "\u226E",
  NotLessEqual: "\u2270",
  NotPrecedes: "\u2280",
  NotPrecedesSlantEqual: "\u22E0",
  NotRightTriangle: "\u22EB",
  NotRightTriangleEqual: "\u22ED",
  NotSubsetEqual: "\u2288",
  NotSucceeds: "\u2281",
  NotSucceedsSlantEqual: "\u22E1",
  NotSupersetEqual: "\u2289",
  NotTilde: "\u2241",
  NotVerticalBar: "\u2224",
  Omega: "\u03A9",
  OverBar: "\u203E",
  OverBrace: "\u23DE",
  PartialD: "\u2202",
  Phi: "\u03A6",
  Pi: "\u03A0",
  PlusMinus: "\xB1",
  Precedes: "\u227A",
  PrecedesEqual: "\u2AAF",
  PrecedesSlantEqual: "\u227C",
  PrecedesTilde: "\u227E",
  Product: "\u220F",
  Proportional: "\u221D",
  Psi: "\u03A8",
  Rarr: "\u21A0",
  Re: "\u211C",
  ReverseEquilibrium: "\u21CB",
  RightAngleBracket: "\u27E9",
  RightArrow: "\u2192",
  RightArrowLeftArrow: "\u21C4",
  RightCeiling: "\u2309",
  RightDownVector: "\u21C2",
  RightFloor: "\u230B",
  RightTee: "\u22A2",
  RightTeeArrow: "\u21A6",
  RightTriangle: "\u22B3",
  RightTriangleEqual: "\u22B5",
  RightUpVector: "\u21BE",
  RightVector: "\u21C0",
  Rightarrow: "\u21D2",
  Rrightarrow: "\u21DB",
  Rsh: "\u21B1",
  Sigma: "\u03A3",
  SmallCircle: "\u2218",
  Sqrt: "\u221A",
  Square: "\u25A1",
  SquareIntersection: "\u2293",
  SquareSubset: "\u228F",
  SquareSubsetEqual: "\u2291",
  SquareSuperset: "\u2290",
  SquareSupersetEqual: "\u2292",
  SquareUnion: "\u2294",
  Star: "\u22C6",
  Subset: "\u22D0",
  SubsetEqual: "\u2286",
  Succeeds: "\u227B",
  SucceedsEqual: "\u2AB0",
  SucceedsSlantEqual: "\u227D",
  SucceedsTilde: "\u227F",
  SuchThat: "\u220B",
  Sum: "\u2211",
  Superset: "\u2283",
  SupersetEqual: "\u2287",
  Supset: "\u22D1",
  Therefore: "\u2234",
  Theta: "\u0398",
  Tilde: "\u223C",
  TildeEqual: "\u2243",
  TildeFullEqual: "\u2245",
  TildeTilde: "\u2248",
  UnderBar: "_",
  UnderBrace: "\u23DF",
  Union: "\u22C3",
  UnionPlus: "\u228E",
  UpArrow: "\u2191",
  UpDownArrow: "\u2195",
  UpTee: "\u22A5",
  Uparrow: "\u21D1",
  Updownarrow: "\u21D5",
  Upsilon: "\u03A5",
  Vdash: "\u22A9",
  Vee: "\u22C1",
  VerticalBar: "\u2223",
  VerticalTilde: "\u2240",
  Vvdash: "\u22AA",
  Wedge: "\u22C0",
  Xi: "\u039E",
  amp: "&",
  acute: "\xB4",
  aleph: "\u2135",
  alpha: "\u03B1",
  amalg: "\u2A3F",
  and: "\u2227",
  ang: "\u2220",
  angmsd: "\u2221",
  angsph: "\u2222",
  ape: "\u224A",
  backprime: "\u2035",
  backsim: "\u223D",
  backsimeq: "\u22CD",
  beta: "\u03B2",
  beth: "\u2136",
  between: "\u226C",
  bigcirc: "\u25EF",
  bigodot: "\u2A00",
  bigoplus: "\u2A01",
  bigotimes: "\u2A02",
  bigsqcup: "\u2A06",
  bigstar: "\u2605",
  bigtriangledown: "\u25BD",
  bigtriangleup: "\u25B3",
  biguplus: "\u2A04",
  blacklozenge: "\u29EB",
  blacktriangle: "\u25B4",
  blacktriangledown: "\u25BE",
  blacktriangleleft: "\u25C2",
  bowtie: "\u22C8",
  boxdl: "\u2510",
  boxdr: "\u250C",
  boxminus: "\u229F",
  boxplus: "\u229E",
  boxtimes: "\u22A0",
  boxul: "\u2518",
  boxur: "\u2514",
  bsol: "\\",
  bull: "\u2022",
  cap: "\u2229",
  check: "\u2713",
  chi: "\u03C7",
  circ: "\u02C6",
  circeq: "\u2257",
  circlearrowleft: "\u21BA",
  circlearrowright: "\u21BB",
  circledR: "\xAE",
  circledS: "\u24C8",
  circledast: "\u229B",
  circledcirc: "\u229A",
  circleddash: "\u229D",
  clubs: "\u2663",
  colon: ":",
  comp: "\u2201",
  ctdot: "\u22EF",
  cuepr: "\u22DE",
  cuesc: "\u22DF",
  cularr: "\u21B6",
  cup: "\u222A",
  curarr: "\u21B7",
  curlyvee: "\u22CE",
  curlywedge: "\u22CF",
  dagger: "\u2020",
  daleth: "\u2138",
  ddarr: "\u21CA",
  deg: "\xB0",
  delta: "\u03B4",
  digamma: "\u03DD",
  div: "\xF7",
  divideontimes: "\u22C7",
  dot: "\u02D9",
  doteqdot: "\u2251",
  dotplus: "\u2214",
  dotsquare: "\u22A1",
  dtdot: "\u22F1",
  ecir: "\u2256",
  efDot: "\u2252",
  egs: "\u2A96",
  ell: "\u2113",
  els: "\u2A95",
  empty: "\u2205",
  epsi: "\u03B5",
  epsiv: "\u03F5",
  erDot: "\u2253",
  eta: "\u03B7",
  eth: "\xF0",
  flat: "\u266D",
  fork: "\u22D4",
  frown: "\u2322",
  gEl: "\u2A8C",
  gamma: "\u03B3",
  gap: "\u2A86",
  gimel: "\u2137",
  gnE: "\u2269",
  gnap: "\u2A8A",
  gne: "\u2A88",
  gnsim: "\u22E7",
  gt: ">",
  gtdot: "\u22D7",
  harrw: "\u21AD",
  hbar: "\u210F",
  hellip: "\u2026",
  hookleftarrow: "\u21A9",
  hookrightarrow: "\u21AA",
  imath: "\u0131",
  infin: "\u221E",
  intcal: "\u22BA",
  iota: "\u03B9",
  jmath: "\u0237",
  kappa: "\u03BA",
  kappav: "\u03F0",
  lEg: "\u2A8B",
  lambda: "\u03BB",
  lap: "\u2A85",
  larrlp: "\u21AB",
  larrtl: "\u21A2",
  lbrace: "{",
  lbrack: "[",
  le: "\u2264",
  leftleftarrows: "\u21C7",
  leftthreetimes: "\u22CB",
  lessdot: "\u22D6",
  lmoust: "\u23B0",
  lnE: "\u2268",
  lnap: "\u2A89",
  lne: "\u2A87",
  lnsim: "\u22E6",
  longmapsto: "\u27FC",
  looparrowright: "\u21AC",
  lowast: "\u2217",
  loz: "\u25CA",
  lt: "<",
  ltimes: "\u22C9",
  ltri: "\u25C3",
  macr: "\xAF",
  malt: "\u2720",
  mho: "\u2127",
  mu: "\u03BC",
  multimap: "\u22B8",
  nLeftarrow: "\u21CD",
  nLeftrightarrow: "\u21CE",
  nRightarrow: "\u21CF",
  nVDash: "\u22AF",
  nVdash: "\u22AE",
  natur: "\u266E",
  nearr: "\u2197",
  nharr: "\u21AE",
  nlarr: "\u219A",
  not: "\xAC",
  nrarr: "\u219B",
  nu: "\u03BD",
  nvDash: "\u22AD",
  nvdash: "\u22AC",
  nwarr: "\u2196",
  omega: "\u03C9",
  omicron: "\u03BF",
  or: "\u2228",
  osol: "\u2298",
  period: ".",
  phi: "\u03C6",
  phiv: "\u03D5",
  pi: "\u03C0",
  piv: "\u03D6",
  prap: "\u2AB7",
  precnapprox: "\u2AB9",
  precneqq: "\u2AB5",
  precnsim: "\u22E8",
  prime: "\u2032",
  psi: "\u03C8",
  quot: '"',
  rarrtl: "\u21A3",
  rbrace: "}",
  rbrack: "]",
  rho: "\u03C1",
  rhov: "\u03F1",
  rightrightarrows: "\u21C9",
  rightthreetimes: "\u22CC",
  ring: "\u02DA",
  rmoust: "\u23B1",
  rtimes: "\u22CA",
  rtri: "\u25B9",
  scap: "\u2AB8",
  scnE: "\u2AB6",
  scnap: "\u2ABA",
  scnsim: "\u22E9",
  sdot: "\u22C5",
  searr: "\u2198",
  sect: "\xA7",
  sharp: "\u266F",
  sigma: "\u03C3",
  sigmav: "\u03C2",
  simne: "\u2246",
  smile: "\u2323",
  spades: "\u2660",
  sub: "\u2282",
  subE: "\u2AC5",
  subnE: "\u2ACB",
  subne: "\u228A",
  supE: "\u2AC6",
  supnE: "\u2ACC",
  supne: "\u228B",
  swarr: "\u2199",
  tau: "\u03C4",
  theta: "\u03B8",
  thetav: "\u03D1",
  tilde: "\u02DC",
  times: "\xD7",
  triangle: "\u25B5",
  triangleq: "\u225C",
  upsi: "\u03C5",
  upuparrows: "\u21C8",
  veebar: "\u22BB",
  vellip: "\u22EE",
  weierp: "\u2118",
  xi: "\u03BE",
  yen: "\xA5",
  zeta: "\u03B6",
  zigrarr: "\u21DD",
  nbsp: "\xA0",
  rsquo: "\u2019",
  lsquo: "\u2018"
};
var loaded = {};
function translate(text) {
  return text.replace(/&([a-z][a-z0-9]*|#(?:[0-9]+|x[0-9a-f]+));/gi, replace);
}
function replace(match, entity) {
  if (entity.charAt(0) === "#") {
    return numeric(entity.slice(1));
  }
  if (entities[entity]) {
    return entities[entity];
  }
  if (options["loadMissingEntities"]) {
    const file = entity.match(/^[a-zA-Z](fr|scr|opf)$/) ? RegExp.$1 : entity.charAt(0).toLowerCase();
    if (!loaded[file]) {
      loaded[file] = true;
      retryAfter(asyncLoad("./util/entities/" + file + ".js"));
    }
  }
  return match;
}
function numeric(entity) {
  const n = entity.charAt(0) === "x" ? parseInt(entity.slice(1), 16) : parseInt(entity);
  return String.fromCodePoint(n);
}

// node_modules/@mathjax/src/mjs/input/tex/ParseUtil.js
var KeyValueDef = class {
  static oneof(...values) {
    return new this("string", (value) => values.includes(value), (value) => value);
  }
  constructor(name, verify, convert) {
    this.name = name;
    this.verify = verify;
    this.convert = convert;
  }
};
var KeyValueTypes = {
  boolean: new KeyValueDef("boolean", (value) => value === "true" || value === "false", (value) => value === "true"),
  number: new KeyValueDef("number", (value) => !!value.match(/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?$/), (value) => parseFloat(value)),
  integer: new KeyValueDef("integer", (value) => !!value.match(/^[-+]?\d+$/), (value) => parseInt(value)),
  string: new KeyValueDef("string", (_value) => true, (value) => value),
  dimen: new KeyValueDef("dimen", (value) => UnitUtil.matchDimen(value)[0] !== null, (value) => value)
};
function readKeyval(text, l3keys = false) {
  const options2 = {};
  let rest = text;
  let end, key, val;
  let dropBrace = true;
  while (rest) {
    [key, end, rest] = readValue(rest, ["=", ","], l3keys, dropBrace);
    dropBrace = false;
    if (end === "=") {
      [val, end, rest] = readValue(rest, [","], l3keys);
      val = val === "false" || val === "true" ? JSON.parse(val) : val;
      options2[key] = val;
    } else if (key) {
      options2[key] = true;
    }
  }
  return options2;
}
function removeBraces(text, count) {
  if (count === 0) {
    return text.replace(/^\s+/, "").replace(/([^\\\s]|^)((?:\\\\)*(?:\\\s)?)?\s+$/, "$1$2");
  }
  while (count > 0) {
    text = text.trim().slice(1, -1);
    count--;
  }
  return text;
}
function readValue(text, end, l3keys = false, dropBrace = false) {
  const length = text.length;
  let braces = 0;
  let value = "";
  let index = 0;
  let start = 0;
  let countBraces = true;
  while (index < length) {
    const c = text[index++];
    switch (c) {
      case "\\":
        value += c + (text[index++] || "");
        countBraces = false;
        continue;
      case " ":
        break;
      case "{":
        if (countBraces) {
          start++;
        }
        braces++;
        break;
      case "}":
        if (!braces) {
          throw new TexError_default("ExtraCloseMissingOpen", "Extra close brace or missing open brace");
        }
        braces--;
        countBraces = false;
        break;
      default:
        if (!braces && end.includes(c)) {
          return [
            removeBraces(value, l3keys ? Math.min(1, start) : start),
            c,
            text.slice(index)
          ];
        }
        if (start > braces) {
          start = braces;
        }
        countBraces = false;
    }
    value += c;
  }
  if (braces) {
    throw new TexError_default("ExtraOpenMissingClose", "Extra open brace or missing close brace");
  }
  return dropBrace && start ? ["", "", removeBraces(value, 1)] : [
    removeBraces(value, l3keys ? Math.min(1, start) : start),
    "",
    text.slice(index)
  ];
}
var ParseUtil = {
  cols(...W) {
    return W.map((n) => UnitUtil.em(n)).join(" ");
  },
  fenced(configuration, open, mml, close, big = "", color = "") {
    const nf = configuration.nodeFactory;
    const mrow = nf.create("node", "mrow", [], {
      open,
      close,
      texClass: TEXCLASS.INNER
    });
    let mo;
    if (big) {
      mo = new TexParser("\\" + big + "l" + open, configuration.parser.stack.env, configuration).mml();
    } else {
      const openNode = nf.create("text", open);
      mo = nf.create("node", "mo", [], {
        fence: true,
        stretchy: true,
        symmetric: true,
        texClass: TEXCLASS.OPEN
      }, openNode);
    }
    NodeUtil_default.appendChildren(mrow, [mo, mml]);
    if (big) {
      mo = new TexParser("\\" + big + "r" + close, configuration.parser.stack.env, configuration).mml();
    } else {
      const closeNode = nf.create("text", close);
      mo = nf.create("node", "mo", [], {
        fence: true,
        stretchy: true,
        symmetric: true,
        texClass: TEXCLASS.CLOSE
      }, closeNode);
    }
    if (color) {
      mo.attributes.set("mathcolor", color);
    }
    NodeUtil_default.appendChildren(mrow, [mo]);
    return mrow;
  },
  fixedFence(configuration, open, mml, close) {
    const mrow = configuration.nodeFactory.create("node", "mrow", [], {
      open,
      close,
      texClass: TEXCLASS.ORD
    });
    if (open) {
      NodeUtil_default.appendChildren(mrow, [
        ParseUtil.mathPalette(configuration, open, "l")
      ]);
    }
    if (NodeUtil_default.isType(mml, "mrow")) {
      NodeUtil_default.appendChildren(mrow, NodeUtil_default.getChildren(mml));
    } else {
      NodeUtil_default.appendChildren(mrow, [mml]);
    }
    if (close) {
      NodeUtil_default.appendChildren(mrow, [
        ParseUtil.mathPalette(configuration, close, "r")
      ]);
    }
    return mrow;
  },
  mathPalette(configuration, fence, side) {
    if (fence === "{" || fence === "}") {
      fence = "\\" + fence;
    }
    const D = "{\\bigg" + side + " " + fence + "}";
    const T = "{\\big" + side + " " + fence + "}";
    return new TexParser("\\mathchoice" + D + T + T + T, {}, configuration).mml();
  },
  fixInitialMO(configuration, nodes) {
    for (let i = 0, m = nodes.length; i < m; i++) {
      const child = nodes[i];
      if (child && !NodeUtil_default.isType(child, "mspace") && (!NodeUtil_default.isType(child, "TeXAtom") || NodeUtil_default.getChildren(child)[0] && NodeUtil_default.getChildren(NodeUtil_default.getChildren(child)[0]).length)) {
        if (NodeUtil_default.isEmbellished(child) || NodeUtil_default.isType(child, "TeXAtom") && NodeUtil_default.getTexClass(child) === TEXCLASS.REL) {
          const mi = configuration.nodeFactory.create("node", "mi");
          nodes.unshift(mi);
        }
        break;
      }
    }
  },
  internalMath(parser, text, level, font) {
    text = text.replace(/ +/g, " ");
    if (parser.configuration.options.internalMath) {
      return parser.configuration.options.internalMath(parser, text, level, font);
    }
    const mathvariant = font || parser.stack.env.font;
    const def = mathvariant ? { mathvariant } : {};
    let mml = [], i = 0, k = 0, c, node, match = "", braces = 0;
    if (text.match(/\\?[${}\\]|\\\(|\\(?:eq)?ref\s*\{|\\U/)) {
      while (i < text.length) {
        c = text.charAt(i++);
        if (c === "$") {
          if (match === "$" && braces === 0) {
            node = parser.create("node", "TeXAtom", [
              new TexParser(text.slice(k, i - 1), {}, parser.configuration).mml()
            ]);
            mml.push(node);
            match = "";
            k = i;
          } else if (match === "") {
            if (k < i - 1) {
              mml.push(ParseUtil.internalText(parser, text.slice(k, i - 1), def));
            }
            match = "$";
            k = i;
          }
        } else if (c === "{" && match !== "") {
          braces++;
        } else if (c === "}") {
          if (match === "}" && braces === 0) {
            const atom = new TexParser(text.slice(k, i), {}, parser.configuration).mml();
            node = parser.create("node", "TeXAtom", [atom], def);
            mml.push(node);
            match = "";
            k = i;
          } else if (match !== "") {
            if (braces) {
              braces--;
            }
          }
        } else if (c === "\\") {
          if (match === "" && text.substring(i).match(/^(eq)?ref\s*\{/)) {
            const len = RegExp["$&"].length;
            if (k < i - 1) {
              mml.push(ParseUtil.internalText(parser, text.slice(k, i - 1), def));
            }
            match = "}";
            k = i - 1;
            i += len;
          } else {
            c = text.charAt(i++);
            if (c === "(" && match === "") {
              if (k < i - 2) {
                mml.push(ParseUtil.internalText(parser, text.slice(k, i - 2), def));
              }
              match = ")";
              k = i;
            } else if (c === ")" && match === ")" && braces === 0) {
              node = parser.create("node", "TeXAtom", [
                new TexParser(text.slice(k, i - 2), {}, parser.configuration).mml()
              ]);
              mml.push(node);
              match = "";
              k = i;
            } else if (c.match(/[${}\\]/) && match === "") {
              i--;
              text = text.substring(0, i - 1) + text.substring(i);
            } else if (c === "U") {
              const arg = text.substring(i).match(/^\s*(?:([0-9A-F])|\{\s*([0-9A-F]+)\s*\})/);
              if (!arg) {
                throw new TexError_default("BadRawUnicode", "Argument to %1 must a hexadecimal number with 1 to 6 digits", "\\U");
              }
              const c2 = String.fromCodePoint(parseInt(arg[1] || arg[2], 16));
              text = text.substring(0, i - 2) + c2 + text.substring(i + arg[0].length);
              i = i - 2 + c2.length;
            }
          }
        }
      }
      if (match !== "") {
        throw new TexError_default("MathNotTerminated", "Math mode is not properly terminated");
      }
    }
    if (k < text.length) {
      mml.push(ParseUtil.internalText(parser, text.slice(k), def));
    }
    if (level != null) {
      mml = [
        parser.create("node", "mstyle", mml, {
          displaystyle: false,
          scriptlevel: level
        })
      ];
    } else if (mml.length > 1) {
      mml = [parser.create("node", "mrow", mml)];
    }
    return mml;
  },
  internalText(parser, text, def) {
    text = text.replace(/\n+/g, " ").replace(/^ +/, entities.nbsp).replace(/ +$/, entities.nbsp);
    const textNode = parser.create("text", text);
    return parser.create("node", "mtext", [], def, textNode);
  },
  underOver(parser, base, script, pos, stack) {
    ParseUtil.checkMovableLimits(base);
    if (NodeUtil_default.isType(base, "munderover") && NodeUtil_default.isEmbellished(base)) {
      NodeUtil_default.setProperties(NodeUtil_default.getCoreMO(base), {
        lspace: 0,
        rspace: 0
      });
      const mo = parser.create("node", "mo", [], { rspace: 0 });
      base = parser.create("node", "mrow", [mo, base]);
    }
    const mml = parser.create("node", "munderover", [base]);
    NodeUtil_default.setChild(mml, pos === "over" ? mml.over : mml.under, script);
    let node = mml;
    if (stack) {
      node = parser.create("node", "TeXAtom", [
        parser.create("node", "mstyle", [mml], {
          displaystyle: true,
          scriptlevel: 0
        })
      ], {
        texClass: TEXCLASS.OP,
        movesupsub: true
      });
    }
    NodeUtil_default.setProperty(node, "subsupOK", true);
    return node;
  },
  checkMovableLimits(base) {
    const symbol = NodeUtil_default.isType(base, "mo") ? NodeUtil_default.getForm(base) : null;
    if (NodeUtil_default.getProperty(base, "movablelimits") || symbol && symbol[3] && symbol[3].movablelimits) {
      NodeUtil_default.setProperties(base, { movablelimits: false });
    }
  },
  setArrayAlign(array, align, parser) {
    if (!parser) {
      align = UnitUtil.trimSpaces(align || "");
    }
    if (align === "t") {
      array.arraydef.align = "baseline 1";
    } else if (align === "b") {
      array.arraydef.align = "baseline -1";
    } else if (align === "c") {
      array.arraydef.align = "axis";
    } else if (align) {
      if (parser) {
        parser.string = `[${align}]` + parser.string.slice(parser.i);
        parser.i = 0;
      } else {
        array.arraydef.align = align;
      }
    }
    return array;
  },
  substituteArgs(parser, args, str) {
    let text = "";
    let newstring = "";
    let i = 0;
    while (i < str.length) {
      let c = str.charAt(i++);
      if (c === "\\") {
        text += c + str.charAt(i++);
      } else if (c === "#") {
        c = str.charAt(i++);
        if (c === "#") {
          text += c;
        } else {
          if (!c.match(/[1-9]/) || parseInt(c, 10) > args.length) {
            throw new TexError_default("IllegalMacroParam", "Illegal macro parameter reference");
          }
          newstring = ParseUtil.addArgs(parser, ParseUtil.addArgs(parser, newstring, text), args[parseInt(c, 10) - 1]);
          text = "";
        }
      } else {
        text += c;
      }
    }
    return ParseUtil.addArgs(parser, newstring, text);
  },
  addArgs(parser, s1, s2) {
    if (s2.match(/^[a-z]/i) && s1.match(/(^|[^\\])(\\\\)*\\[a-z]+$/i)) {
      s1 += " ";
    }
    if (s1.length + s2.length > parser.configuration.options["maxBuffer"]) {
      throw new TexError_default("MaxBufferSize", "MathJax internal buffer size exceeded; is there a recursive macro call?");
    }
    return s1 + s2;
  },
  checkMaxMacros(parser, isMacro = true) {
    if (++parser.macroCount <= parser.configuration.options["maxMacros"]) {
      return;
    }
    if (isMacro) {
      throw new TexError_default("MaxMacroSub1", "MathJax maximum macro substitution count exceeded; is here a recursive macro call?");
    } else {
      throw new TexError_default("MaxMacroSub2", "MathJax maximum substitution count exceeded; is there a recursive latex environment?");
    }
  },
  checkEqnEnv(parser, nestable = true) {
    const top = parser.stack.Top();
    const first = top.First;
    if (top.getProperty("nestable") && nestable && !first || top.getProperty("nestStart")) {
      return;
    }
    if (!top.isKind("start") || first) {
      throw new TexError_default("ErroneousNestingEq", "Erroneous nesting of equation structures");
    }
  },
  copyNode(node, parser) {
    const tree = node.copy();
    const options2 = parser.configuration;
    tree.walkTree((n) => {
      options2.addNode(n.kind, n);
      const lists = (n.getProperty("in-lists") || "").split(/,/);
      for (const list of lists) {
        if (list) {
          options2.addNode(list, n);
        }
      }
    });
    return tree;
  },
  mmlFilterAttribute(_parser, _name, value) {
    return value;
  },
  getFontDef(parser) {
    const font = parser.stack.env["font"];
    return font ? { mathvariant: font } : {};
  },
  keyvalOptions(attrib, allowed = null, error = false, l3keys = false) {
    const def = readKeyval(attrib, l3keys);
    if (allowed) {
      for (const key of Object.keys(def)) {
        if (Object.hasOwn(allowed, key)) {
          if (allowed[key] instanceof KeyValueDef) {
            const type = allowed[key];
            const value = String(def[key]);
            if (!type.verify(value)) {
              throw new TexError_default("InvalidValue", "Value for key '%1' is not of the expected type", key);
            }
            def[key] = type.convert(value);
          }
        } else {
          if (error) {
            throw new TexError_default("InvalidOption", "Invalid option: %1", key);
          }
          delete def[key];
        }
      }
    }
    return def;
  },
  isLatinOrGreekChar(c) {
    return !!c.normalize("NFD").match(/[a-zA-Z\u0370-\u03F0]/);
  }
};

// node_modules/@mathjax/src/mjs/input/tex/ColumnParser.js
var ColumnParser = class {
  constructor() {
    this.columnHandler = {
      l: (state) => state.calign[state.j++] = "left",
      c: (state) => state.calign[state.j++] = "center",
      r: (state) => state.calign[state.j++] = "right",
      p: (state) => this.getColumn(state, "top"),
      m: (state) => this.getColumn(state, "middle"),
      b: (state) => this.getColumn(state, "bottom"),
      w: (state) => this.getColumn(state, "top", ""),
      W: (state) => this.getColumn(state, "top", ""),
      "|": (state) => this.addRule(state, "solid"),
      ":": (state) => this.addRule(state, "dashed"),
      ">": (state) => state.cstart[state.j] = this.getBraces(state) + (state.cstart[state.j] || ""),
      "<": (state) => state.cend[state.j - 1] = this.getBraces(state) + (state.cend[state.j - 1] || ""),
      "@": (state) => this.addAt(state, this.getBraces(state)),
      "!": (state) => this.addBang(state, this.getBraces(state)),
      "*": (state) => this.repeat(state),
      "{": (state) => this.brace(state),
      P: (state) => this.macroColumn(state, ">{$}p{#1}<{$}", 1),
      M: (state) => this.macroColumn(state, ">{$}m{#1}<{$}", 1),
      B: (state) => this.macroColumn(state, ">{$}b{#1}<{$}", 1),
      " ": (_state) => {
      },
      "\n": (_state_) => {
      }
    };
    this.MAXCOLUMNS = 1e4;
  }
  process(parser, template, array) {
    const state = {
      parser,
      template,
      i: 0,
      j: 0,
      c: "",
      cwidth: [],
      calign: [],
      cspace: [],
      clines: [],
      cstart: array.cstart,
      cend: array.cend,
      ralign: array.ralign,
      cextra: array.cextra
    };
    if (template.charAt(0) === "{" && template.slice(-1) === "}") {
      const braced = this.getBraces(state);
      if (braced.length === template.length - 2) {
        state.template = braced;
      }
      state.i = 0;
    }
    let n = 0;
    while (state.i < state.template.length) {
      if (n++ > this.MAXCOLUMNS) {
        throw new TexError_default("MaxColumns", "Too many column specifiers (perhaps looping column definitions?)");
      }
      const code = state.template.codePointAt(state.i);
      const c = state.c = String.fromCodePoint(code);
      state.i += c.length;
      this.processColumn(state, c);
    }
    this.setColumnAlign(state, array);
    this.setColumnWidths(state, array);
    this.setColumnSpacing(state, array);
    this.setColumnLines(state, array);
    this.setPadding(state, array);
  }
  processColumn(state, c) {
    if (!Object.hasOwn(this.columnHandler, c)) {
      throw new TexError_default("BadPreamToken", "Illegal pream-token (%1)", c);
    }
    this.columnHandler[c](state);
  }
  setColumnAlign(state, array) {
    array.arraydef.columnalign = state.calign.join(" ");
  }
  setColumnWidths(state, array) {
    if (!state.cwidth.length)
      return;
    const cwidth = [...state.cwidth];
    if (cwidth.length < state.calign.length) {
      cwidth.push("auto");
    }
    array.arraydef.columnwidth = cwidth.map((w) => w || "auto").join(" ");
  }
  setColumnSpacing(state, array) {
    if (!state.cspace.length)
      return;
    const cspace = [...state.cspace];
    if (cspace.length < state.calign.length) {
      cspace.push("1em");
    }
    array.arraydef.columnspacing = cspace.slice(1).map((d) => d || "1em").join(" ");
  }
  setColumnLines(state, array) {
    if (!state.clines.length)
      return;
    const clines = [...state.clines];
    if (clines[0]) {
      array.frame.push(["left", clines[0]]);
    }
    if (clines.length > state.calign.length) {
      array.frame.push(["right", clines.pop()]);
    } else if (clines.length < state.calign.length) {
      clines.push("none");
    }
    if (clines.length > 1) {
      array.arraydef.columnlines = clines.slice(1).map((l) => l || "none").join(" ");
    }
  }
  setPadding(state, array) {
    if (!state.cextra[0] && !state.cextra[state.calign.length - 1])
      return;
    const i = state.calign.length - 1;
    const cspace = state.cspace;
    const space = !state.cextra[i] ? null : cspace[i];
    array.arraydef["data-array-padding"] = `${cspace[0] || ".5em"} ${space || ".5em"}`;
  }
  getColumn(state, ralign, calign = "left") {
    state.calign[state.j] = calign || this.getAlign(state);
    state.cwidth[state.j] = this.getDimen(state);
    state.ralign[state.j] = [
      ralign,
      state.cwidth[state.j],
      state.calign[state.j]
    ];
    state.j++;
  }
  getDimen(state) {
    const dim = this.getBraces(state);
    if (!UnitUtil.matchDimen(dim)[0]) {
      throw new TexError_default("MissingColumnDimOrUnits", "Missing dimension or its units for %1 column declaration", state.c);
    }
    return dim;
  }
  getAlign(state) {
    const align = this.getBraces(state);
    return lookup(align.toLowerCase(), { l: "left", c: "center", r: "right" }, "");
  }
  getBraces(state) {
    while (state.template[state.i] === " ")
      state.i++;
    if (state.i >= state.template.length) {
      throw new TexError_default("MissingArgForColumn", "Missing argument for %1 column declaration", state.c);
    }
    if (state.template[state.i] !== "{") {
      return state.template[state.i++];
    }
    const i = ++state.i;
    let braces = 1;
    while (state.i < state.template.length) {
      switch (state.template.charAt(state.i++)) {
        case "\\":
          state.i++;
          break;
        case "{":
          braces++;
          break;
        case "}":
          if (--braces === 0) {
            return state.template.slice(i, state.i - 1);
          }
          break;
      }
    }
    throw new TexError_default("MissingCloseBrace", "Missing close brace");
  }
  macroColumn(state, macro, n) {
    const args = [];
    while (n > 0 && n--) {
      args.push(this.getBraces(state));
    }
    state.template = ParseUtil.substituteArgs(state.parser, args, macro) + state.template.slice(state.i);
    state.i = 0;
  }
  addRule(state, rule) {
    if (state.clines[state.j]) {
      this.addAt(state, "\\,");
    }
    state.clines[state.j] = rule;
    if (state.cspace[state.j] === "0") {
      state.cstart[state.j] = "\\hspace{.5em}";
    }
  }
  addAt(state, macro) {
    const { cstart, cspace, j } = state;
    state.cextra[j] = true;
    state.calign[j] = "center";
    if (state.clines[j]) {
      if (cspace[j] === ".5em") {
        cstart[j - 1] += "\\hspace{.25em}";
      } else if (!cspace[j]) {
        state.cend[j - 1] = (state.cend[j - 1] || "") + "\\hspace{.5em}";
      }
    }
    cstart[j] = macro;
    cspace[j] = "0";
    cspace[++state.j] = "0";
  }
  addBang(state, macro) {
    const { cstart, cspace, j } = state;
    state.cextra[j] = true;
    state.calign[j] = "center";
    cstart[j] = (cspace[j] === "0" && state.clines[j] ? "\\hspace{.25em}" : "") + macro;
    if (!cspace[j]) {
      cspace[j] = ".5em";
    }
    cspace[++state.j] = ".5em";
  }
  repeat(state) {
    const num = this.getBraces(state);
    const cols = this.getBraces(state);
    const n = parseInt(num);
    if (String(n) !== num) {
      throw new TexError_default("ColArgNotNum", "First argument to %1 column specifier must be a number", "*");
    }
    state.template = new Array(n).fill(cols).join("") + state.template.substring(state.i);
    state.i = 0;
  }
  brace(state) {
    state.i--;
    this.processColumn(state, this.getBraces(state));
  }
};

// node_modules/@mathjax/src/mjs/input/tex/ParseOptions.js
var MATHVARIANT = TexConstant.Variant;
var ParseOptions = class _ParseOptions {
  constructor(configuration, options2 = []) {
    this.options = {};
    this.columnParser = new ColumnParser();
    this.packageData = /* @__PURE__ */ new Map();
    this.parsers = [];
    this.root = null;
    this.nodeLists = {};
    this.error = false;
    this.handlers = configuration.handlers;
    this.nodeFactory = new NodeFactory();
    this.nodeFactory.configuration = this;
    this.nodeFactory.setCreators(configuration.nodes);
    this.itemFactory = new StackItemFactory_default(configuration.items);
    this.itemFactory.configuration = this;
    defaultOptions(this.options, ...options2);
    defaultOptions(this.options, configuration.options);
    this.mathStyle = _ParseOptions.getVariant.get(this.options.mathStyle) || _ParseOptions.getVariant.get("TeX");
  }
  pushParser(parser) {
    this.parsers.unshift(parser);
  }
  popParser() {
    this.parsers.shift();
  }
  get parser() {
    return this.parsers[0];
  }
  clear() {
    this.parsers = [];
    this.root = null;
    this.nodeLists = {};
    this.error = false;
    this.tags.resetTag();
  }
  addNode(property, node) {
    let list = this.nodeLists[property];
    if (!list) {
      list = this.nodeLists[property] = [];
    }
    list.push(node);
    if (node.kind !== property) {
      const inlists = NodeUtil_default.getProperty(node, "in-lists") || "";
      const lists = (inlists ? inlists.split(/,/) : []).concat(property).join(",");
      NodeUtil_default.setProperty(node, "in-lists", lists);
    }
  }
  getList(property) {
    const list = this.nodeLists[property] || [];
    const result = [];
    for (const node of list) {
      if (this.inTree(node)) {
        result.push(node);
      }
    }
    this.nodeLists[property] = result;
    return result;
  }
  removeFromList(property, nodes) {
    const list = this.nodeLists[property] || [];
    for (const node of nodes) {
      const i = list.indexOf(node);
      if (i >= 0) {
        list.splice(i, 1);
      }
    }
  }
  inTree(node) {
    while (node && node !== this.root) {
      node = node.parent;
    }
    return !!node;
  }
};
ParseOptions.getVariant = /* @__PURE__ */ new Map([
  [
    "TeX",
    (c, b) => b ? c.match(/^[\u0391-\u03A9\u03F4]/) ? MATHVARIANT.NORMAL : "" : ""
  ],
  ["ISO", (_c) => MATHVARIANT.ITALIC],
  [
    "French",
    (c) => c.normalize("NFD").match(/^[a-z]/) ? MATHVARIANT.ITALIC : MATHVARIANT.NORMAL
  ],
  ["upright", (_c) => MATHVARIANT.NORMAL]
]);
var ParseOptions_default = ParseOptions;

// node_modules/@mathjax/src/mjs/input/tex/Tags.js
var Label = class {
  constructor(tag = "???", id = "") {
    this.tag = tag;
    this.id = id;
  }
};
var TagInfo = class {
  constructor(env = "", taggable = false, defaultTags2 = false, tag = null, tagId = "", tagFormat = "", noTag = false, labelId = "") {
    this.env = env;
    this.taggable = taggable;
    this.defaultTags = defaultTags2;
    this.tag = tag;
    this.tagId = tagId;
    this.tagFormat = tagFormat;
    this.noTag = noTag;
    this.labelId = labelId;
  }
};
var AbstractTags = class {
  constructor() {
    this.counter = 0;
    this.allCounter = 0;
    this.configuration = null;
    this.ids = {};
    this.allIds = {};
    this.labels = {};
    this.allLabels = {};
    this.redo = false;
    this.refUpdate = false;
    this.currentTag = new TagInfo();
    this.history = [];
    this.stack = [];
    this.enTag = function(node, tag) {
      const nf = this.configuration.nodeFactory;
      const cell = nf.create("node", "mtd", [node]);
      const row = nf.create("node", "mlabeledtr", [tag, cell]);
      const table = nf.create("node", "mtable", [row], {
        side: this.configuration.options["tagSide"],
        minlabelspacing: this.configuration.options["tagIndent"],
        displaystyle: true
      });
      return table;
    };
  }
  start(env, taggable, defaultTags2) {
    if (this.currentTag) {
      this.stack.push(this.currentTag);
    }
    const label = this.label;
    this.currentTag = new TagInfo(env, taggable, defaultTags2);
    this.label = label;
  }
  get env() {
    return this.currentTag.env;
  }
  end() {
    this.history.push(this.currentTag);
    const label = this.label;
    this.currentTag = this.stack.pop();
    if (label && !this.label) {
      this.label = label;
    }
  }
  tag(tag, noFormat) {
    this.currentTag.tag = tag;
    this.currentTag.tagFormat = noFormat ? tag : this.formatTag(tag);
    this.currentTag.noTag = false;
  }
  notag() {
    this.tag("", true);
    this.currentTag.noTag = true;
  }
  get noTag() {
    return this.currentTag.noTag;
  }
  set label(label) {
    this.currentTag.labelId = label;
  }
  get label() {
    return this.currentTag.labelId;
  }
  formatUrl(id, base) {
    return base + "#" + encodeURIComponent(id);
  }
  formatTag(tag) {
    return ["(", tag, ")"];
  }
  formatRef(tag) {
    return this.formatTag(tag);
  }
  formatId(id) {
    return "mjx-eqn:" + id.replace(/\s/g, "_");
  }
  formatNumber(n) {
    return n.toString();
  }
  autoTag() {
    if (this.currentTag.tag == null) {
      this.counter++;
      this.tag(this.formatNumber(this.counter), false);
    }
  }
  clearTag() {
    this.tag(null, true);
    this.currentTag.tagId = "";
  }
  getTag(force = false) {
    if (force) {
      this.autoTag();
      return this.makeTag();
    }
    const ct = this.currentTag;
    if (ct.taggable && !ct.noTag) {
      if (ct.defaultTags) {
        this.autoTag();
      }
      if (ct.tag) {
        return this.makeTag();
      }
    }
    return null;
  }
  resetTag() {
    this.history = [];
    this.redo = false;
    this.refUpdate = false;
    this.clearTag();
  }
  reset(offset = 0) {
    this.resetTag();
    this.counter = this.allCounter = offset;
    this.allLabels = {};
    this.allIds = {};
    this.label = "";
  }
  startEquation(math) {
    this.history = [];
    this.stack = [];
    this.clearTag();
    this.currentTag = new TagInfo("", void 0, void 0);
    this.labels = {};
    this.ids = {};
    this.counter = this.allCounter;
    this.redo = false;
    const recompile = math.inputData.recompile;
    if (recompile) {
      this.refUpdate = true;
      this.counter = recompile.counter;
    }
  }
  finishEquation(math) {
    if (this.redo) {
      math.inputData.recompile = {
        state: math.state(),
        counter: this.allCounter
      };
    }
    if (!this.refUpdate) {
      this.allCounter = this.counter;
    }
    Object.assign(this.allIds, this.ids);
    Object.assign(this.allLabels, this.labels);
  }
  finalize(node, env) {
    if (!env.display || this.currentTag.env || this.currentTag.tag == null) {
      return node;
    }
    const tag = this.makeTag();
    const table = this.enTag(node, tag);
    return table;
  }
  makeId() {
    this.currentTag.tagId = this.formatId(this.configuration.options["useLabelIds"] ? this.label || this.currentTag.tag : this.currentTag.tag);
  }
  makeTag() {
    var _a;
    this.makeId();
    if (this.label) {
      this.labels[this.label] = new Label(this.currentTag.tag, this.currentTag.tagId);
      this.label = "";
    }
    const format = this.currentTag.tagFormat;
    const tag = Array.isArray(format) ? format : ((_a = format.match(/^(\(|\[|\{)(.*)(\}|\]|\))$/)) === null || _a === void 0 ? void 0 : _a.slice(1)) || [format];
    const mml = new TexParser(tag.map((part) => part ? `\\text{${part}}` : "").join(""), {}, this.configuration).mml();
    return this.configuration.nodeFactory.create("node", "mtd", [mml], {
      id: this.currentTag.tagId,
      rowalign: this.configuration.options.tagAlign
    });
  }
};
var NoTags = class extends AbstractTags {
  autoTag() {
  }
  getTag() {
    return !this.currentTag.tag ? null : super.getTag();
  }
};
var AllTags = class extends AbstractTags {
  finalize(node, env) {
    if (!env.display || this.history.find(function(x) {
      return x.taggable;
    })) {
      return node;
    }
    const tag = this.getTag(true);
    return this.enTag(node, tag);
  }
};
var tagsMapping = /* @__PURE__ */ new Map([
  ["none", NoTags],
  ["all", AllTags]
]);
var defaultTags = "none";
var TagsFactory = {
  OPTIONS: {
    tags: defaultTags,
    tagSide: "right",
    tagIndent: "0.8em",
    useLabelIds: true,
    ignoreDuplicateLabels: false,
    tagAlign: "baseline"
  },
  add(name, constr) {
    tagsMapping.set(name, constr);
  },
  addTags(tags) {
    for (const key of Object.keys(tags)) {
      TagsFactory.add(key, tags[key]);
    }
  },
  create(name) {
    const constr = tagsMapping.get(name) || tagsMapping.get(defaultTags);
    if (!constr) {
      throw Error("Unknown tags class");
    }
    return new constr();
  },
  setDefault(name) {
    defaultTags = name;
  },
  getDefault() {
    return TagsFactory.create(defaultTags);
  }
};

// node_modules/@mathjax/src/mjs/input/tex/Token.js
var Token = class {
  constructor(_token, _char, _attributes) {
    this._token = _token;
    this._char = _char;
    this._attributes = _attributes;
  }
  get token() {
    return this._token;
  }
  get char() {
    return this._char;
  }
  get attributes() {
    return this._attributes;
  }
};
var Macro = class {
  constructor(_token, _func, _args = []) {
    this._token = _token;
    this._func = _func;
    this._args = _args;
  }
  get token() {
    return this._token;
  }
  get func() {
    return this._func;
  }
  get args() {
    return this._args;
  }
};

// node_modules/@mathjax/src/mjs/input/tex/TokenMap.js
function parseResult(result) {
  return result === void 0 ? true : result;
}
var AbstractTokenMap = class {
  constructor(_name, _parser) {
    this._name = _name;
    this._parser = _parser;
    MapHandler.register(this);
  }
  get name() {
    return this._name;
  }
  parserFor(token) {
    return this.contains(token) ? this.parser : null;
  }
  parse([env, token]) {
    const parser = this.parserFor(token);
    const mapped = this.lookup(token);
    return parser && mapped ? parseResult(parser(env, mapped)) : null;
  }
  set parser(parser) {
    this._parser = parser;
  }
  get parser() {
    return this._parser;
  }
};
var RegExpMap = class extends AbstractTokenMap {
  constructor(name, parser, _regExp) {
    super(name, parser);
    this._regExp = _regExp;
  }
  contains(token) {
    return this._regExp.test(token);
  }
  lookup(token) {
    return this.contains(token) ? token : null;
  }
};
var AbstractParseMap = class extends AbstractTokenMap {
  constructor() {
    super(...arguments);
    this.map = /* @__PURE__ */ new Map();
  }
  lookup(token) {
    return this.map.get(token);
  }
  contains(token) {
    return this.map.has(token);
  }
  add(token, object) {
    this.map.set(token, object);
  }
  remove(token) {
    this.map.delete(token);
  }
};
var CharacterMap = class extends AbstractParseMap {
  constructor(name, parser, json) {
    super(name, parser);
    for (const key of Object.keys(json)) {
      const value = json[key];
      const [char, attrs] = typeof value === "string" ? [value, null] : value;
      const character = new Token(key, char, attrs);
      this.add(key, character);
    }
  }
};
var DelimiterMap = class extends CharacterMap {
  parse([env, token]) {
    return super.parse([env, "\\" + token]);
  }
};
var MacroMap = class extends AbstractParseMap {
  constructor(name, json, functionMap = {}) {
    super(name, null);
    const getMethod = (func) => typeof func === "string" ? functionMap[func] : func;
    for (const [key, value] of Object.entries(json)) {
      let func;
      let args;
      if (Array.isArray(value)) {
        func = getMethod(value[0]);
        args = value.slice(1);
      } else {
        func = getMethod(value);
        args = [];
      }
      const character = new Macro(key, func, args);
      this.add(key, character);
    }
  }
  parserFor(token) {
    const macro = this.lookup(token);
    return macro ? macro.func : null;
  }
  parse([env, token]) {
    const macro = this.lookup(token);
    const parser = this.parserFor(token);
    if (!macro || !parser) {
      return null;
    }
    return parseResult(parser(env, macro.token, ...macro.args));
  }
};
var CommandMap = class extends MacroMap {
  parse([env, token]) {
    const macro = this.lookup(token);
    const parser = this.parserFor(token);
    if (!macro || !parser) {
      return null;
    }
    const saveCommand = env.currentCS;
    env.currentCS = "\\" + token;
    const result = parser(env, "\\" + macro.token, ...macro.args);
    env.currentCS = saveCommand;
    return parseResult(result);
  }
};
var EnvironmentMap = class extends MacroMap {
  constructor(name, parser, json, functionMap = {}) {
    super(name, json, functionMap);
    this.parser = parser;
  }
  parse([env, token]) {
    const macro = this.lookup(token);
    const envParser = this.parserFor(token);
    if (!macro || !envParser) {
      return null;
    }
    return parseResult(this.parser(env, macro.token, envParser, macro.args));
  }
};

// node_modules/@mathjax/src/mjs/input/tex/MapHandler.js
var maps = /* @__PURE__ */ new Map();
var MapHandler = {
  register(map) {
    maps.set(map.name, map);
  },
  getMap(name) {
    return maps.get(name);
  }
};
var SubHandler = class _SubHandler {
  constructor() {
    this._configuration = new PrioritizedList();
    this._fallback = new FunctionList();
  }
  add(maps3, fallback, priority = PrioritizedList.DEFAULTPRIORITY) {
    for (const name of maps3.slice().reverse()) {
      const map = MapHandler.getMap(name);
      if (!map) {
        this.warn(`Configuration '${name}' not found! Omitted.`);
        return;
      }
      this._configuration.add(map, priority);
    }
    if (fallback) {
      this._fallback.add(fallback, priority);
    }
  }
  remove(maps3, fallback = null) {
    for (const name of maps3) {
      const map = this.retrieve(name);
      if (map) {
        this._configuration.remove(map);
      }
    }
    if (fallback) {
      this._fallback.remove(fallback);
    }
  }
  parse(input) {
    for (const { item: map } of this._configuration) {
      const result = map.parse(input);
      if (result === _SubHandler.FALLBACK) {
        break;
      }
      if (result) {
        return result;
      }
    }
    const [env, token] = input;
    Array.from(this._fallback)[0].item(env, token);
    return;
  }
  lookup(token) {
    const map = this.applicable(token);
    return map ? map.lookup(token) : null;
  }
  contains(token) {
    const map = this.applicable(token);
    return !!map && !(map instanceof CharacterMap && map.lookup(token).char === null);
  }
  toString() {
    const names = [];
    for (const { item: map } of this._configuration) {
      names.push(map.name);
    }
    return names.join(", ");
  }
  applicable(token) {
    for (const { item: map } of this._configuration) {
      if (map.contains(token)) {
        return map;
      }
    }
    return null;
  }
  retrieve(name) {
    for (const { item: map } of this._configuration) {
      if (map.name === name) {
        return map;
      }
    }
    return null;
  }
  warn(message) {
    console.log("TexParser Warning: " + message);
  }
};
SubHandler.FALLBACK = Symbol("fallback");
var SubHandlers = class {
  constructor() {
    this.map = /* @__PURE__ */ new Map();
  }
  add(handlers, fallbacks, priority = PrioritizedList.DEFAULTPRIORITY) {
    for (const key of Object.keys(handlers)) {
      const name = key;
      let subHandler = this.get(name);
      if (!subHandler) {
        subHandler = new SubHandler();
        this.set(name, subHandler);
      }
      subHandler.add(handlers[name], fallbacks[name], priority);
    }
  }
  remove(handlers, fallbacks) {
    for (const name of Object.keys(handlers)) {
      const subHandler = this.get(name);
      if (subHandler) {
        subHandler.remove(handlers[name], fallbacks[name]);
      }
    }
  }
  set(name, subHandler) {
    this.map.set(name, subHandler);
  }
  get(name) {
    return this.map.get(name);
  }
  retrieve(name) {
    for (const handler of this.map.values()) {
      const map = handler.retrieve(name);
      if (map) {
        return map;
      }
    }
    return null;
  }
  keys() {
    return this.map.keys();
  }
};

// node_modules/@mathjax/src/mjs/input/tex/Configuration.js
var Configuration = class _Configuration {
  static makeProcessor(func, priority) {
    return Array.isArray(func) ? func : [func, priority];
  }
  static _create(name, config = {}) {
    var _a;
    const priority = (_a = config.priority) !== null && _a !== void 0 ? _a : PrioritizedList.DEFAULTPRIORITY;
    const init = config.init ? this.makeProcessor(config.init, priority) : null;
    const conf = config.config ? this.makeProcessor(config.config, priority) : null;
    const preprocessors = (config.preprocessors || []).map((pre) => this.makeProcessor(pre, priority));
    const postprocessors = (config.postprocessors || []).map((post) => this.makeProcessor(post, priority));
    const parser = config.parser || "tex";
    return new _Configuration(name, config[ConfigurationType.HANDLER] || {}, config[ConfigurationType.FALLBACK] || {}, config[ConfigurationType.ITEMS] || {}, config[ConfigurationType.TAGS] || {}, config[ConfigurationType.OPTIONS] || {}, config[ConfigurationType.NODES] || {}, preprocessors, postprocessors, init, conf, priority, parser);
  }
  static create(name, config = {}) {
    const configuration = _Configuration._create(name, config);
    ConfigurationHandler.set(name, configuration);
    return configuration;
  }
  static local(config = {}) {
    return _Configuration._create("", config);
  }
  constructor(name, handler = {}, fallback = {}, items = {}, tags = {}, options2 = {}, nodes = {}, preprocessors = [], postprocessors = [], initMethod = null, configMethod = null, priority, parser) {
    this.name = name;
    this.handler = handler;
    this.fallback = fallback;
    this.items = items;
    this.tags = tags;
    this.options = options2;
    this.nodes = nodes;
    this.preprocessors = preprocessors;
    this.postprocessors = postprocessors;
    this.initMethod = initMethod;
    this.configMethod = configMethod;
    this.priority = priority;
    this.parser = parser;
    this.handler = Object.assign({
      [HandlerType.CHARACTER]: [],
      [HandlerType.DELIMITER]: [],
      [HandlerType.MACRO]: [],
      [HandlerType.ENVIRONMENT]: []
    }, handler);
  }
  get init() {
    return this.initMethod ? this.initMethod[0] : null;
  }
  get config() {
    return this.configMethod ? this.configMethod[0] : null;
  }
};
var maps2 = /* @__PURE__ */ new Map();
var ConfigurationHandler = {
  set(name, map) {
    maps2.set(name, map);
  },
  get(name) {
    return maps2.get(name);
  },
  keys() {
    return maps2.keys();
  }
};
var ParserConfiguration = class {
  constructor(packages, parsers = ["tex"]) {
    this.initMethod = new FunctionList();
    this.configMethod = new FunctionList();
    this.configurations = new PrioritizedList();
    this.parsers = [];
    this.handlers = new SubHandlers();
    this.items = {};
    this.tags = {};
    this.options = {};
    this.nodes = {};
    this.parsers = parsers;
    for (const pkg of packages.slice().reverse()) {
      this.addPackage(pkg);
    }
    for (const { item: config, priority } of this.configurations) {
      this.append(config, priority);
    }
  }
  init() {
    this.initMethod.execute(this);
  }
  config(jax) {
    this.configMethod.execute(this, jax);
    for (const config of this.configurations) {
      this.addFilters(jax, config.item);
    }
  }
  addPackage(pkg) {
    const name = typeof pkg === "string" ? pkg : pkg[0];
    const conf = this.getPackage(name);
    if (conf) {
      this.configurations.add(conf, typeof pkg === "string" ? conf.priority : pkg[1]);
    }
  }
  add(name, jax, options2 = {}) {
    const config = this.getPackage(name);
    this.append(config);
    this.configurations.add(config, config.priority);
    this.init();
    const parser = jax.parseOptions;
    parser.nodeFactory.setCreators(config.nodes);
    for (const kind of Object.keys(config.items)) {
      parser.itemFactory.setNodeClass(kind, config.items[kind]);
    }
    TagsFactory.addTags(config.tags);
    defaultOptions(parser.options, config.options);
    userOptions(parser.options, options2);
    this.addFilters(jax, config);
    if (config.config) {
      config.config(this, jax);
    }
  }
  getPackage(name) {
    const config = ConfigurationHandler.get(name);
    if (config && !this.parsers.includes(config.parser)) {
      throw Error(`Package '${name}' doesn't target the proper parser`);
    }
    if (!config) {
      this.warn(`Package '${name}' not found.  Omitted.`);
    }
    return config;
  }
  append(config, priority) {
    priority = priority || config.priority;
    if (config.initMethod) {
      this.initMethod.add(config.initMethod[0], config.initMethod[1]);
    }
    if (config.configMethod) {
      this.configMethod.add(config.configMethod[0], config.configMethod[1]);
    }
    this.handlers.add(config.handler, config.fallback, priority);
    Object.assign(this.items, config.items);
    Object.assign(this.tags, config.tags);
    defaultOptions(this.options, config.options);
    Object.assign(this.nodes, config.nodes);
  }
  addFilters(jax, config) {
    for (const [pre, priority] of config.preprocessors) {
      jax.preFilters.add(pre, priority);
    }
    for (const [post, priority] of config.postprocessors) {
      jax.postFilters.add(post, priority);
    }
  }
  warn(message) {
    console.warn("MathJax Warning: " + message);
  }
};

// node_modules/@mathjax/src/mjs/util/Styles.js
var TRBL = ["top", "right", "bottom", "left"];
var WSC = ["width", "style", "color"];
function splitSpaces(text) {
  const parts = text.split(/((?:'[^'\n]*'|"[^"\n]*"|,[\s\n]|[^\s\n])*)/g);
  const split2 = [];
  while (parts.length > 1) {
    parts.shift();
    split2.push(parts.shift());
  }
  return split2;
}
function splitTRBL(name) {
  const parts = splitSpaces(this.styles[name]);
  if (parts.length === 0) {
    parts.push("");
  }
  if (parts.length === 1) {
    parts.push(parts[0]);
  }
  if (parts.length === 2) {
    parts.push(parts[0]);
  }
  if (parts.length === 3) {
    parts.push(parts[1]);
  }
  for (const child of Styles.connect[name].children) {
    this.setStyle(this.childName(name, child), parts.shift());
  }
}
function combineTRBL(name) {
  const children = Styles.connect[name].children;
  const parts = [];
  for (const child of children) {
    const part = this.styles[this.childName(name, child)];
    if (!part) {
      delete this.styles[name];
      return;
    }
    parts.push(part);
  }
  if (parts[3] === parts[1]) {
    parts.pop();
    if (parts[2] === parts[0]) {
      parts.pop();
      if (parts[1] === parts[0]) {
        parts.pop();
      }
    }
  }
  this.styles[name] = parts.join(" ");
}
function combinePart(name) {
  combineTRBL.call(this, name);
  this.combineChildren(name);
  combineSame.call(this, name);
  this.combineParent(name);
}
function splitSame(name) {
  for (const child of Styles.connect[name].children) {
    this.setStyle(this.childName(name, child), this.styles[name]);
  }
}
function combineSame(name) {
  if (!Styles.connect[name])
    return;
  const children = [...Styles.connect[name].children];
  const value = this.styles[this.childName(name, children.shift())];
  for (const child of children) {
    if (this.styles[this.childName(name, child)] !== value) {
      delete this.styles[name];
      return;
    }
  }
  if (value) {
    this.styles[name] = value;
  }
}
var BORDER = {
  width: /^(?:[\d.]+(?:[a-z]+)|thin|medium|thick|inherit|initial|unset)$/,
  style: /^(?:none|hidden|dotted|dashed|solid|double|groove|ridge|inset|outset|inherit|initial|unset)$/
};
function splitWSC(name) {
  const parts = { width: "", style: "", color: "" };
  for (const part of splitSpaces(this.styles[name])) {
    if (part.match(BORDER.width) && parts.width === "") {
      parts.width = part;
    } else if (part.match(BORDER.style) && parts.style === "") {
      parts.style = part;
    } else {
      parts.color = part;
    }
  }
  for (const child of Styles.connect[name].children) {
    this.setStyle(this.childName(name, child), parts[child]);
  }
}
function combineWSC(name) {
  const parts = [];
  for (const child of Styles.connect[name].children) {
    const value = this.styles[this.childName(name, child)];
    if (value) {
      parts.push(value);
    }
  }
  if (parts.length > 1) {
    this.styles[name] = parts.join(" ");
  } else {
    delete this.styles[name];
  }
}
var FONT = {
  style: /^(?:normal|italic|oblique|inherit|initial|unset)$/,
  variant: new RegExp("^(?:" + [
    "normal|none",
    "inherit|initial|unset",
    "common-ligatures|no-common-ligatures",
    "discretionary-ligatures|no-discretionary-ligatures",
    "historical-ligatures|no-historical-ligatures",
    "contextual|no-contextual",
    "(?:stylistic|character-variant|swash|ornaments|annotation)\\([^)]*\\)",
    "small-caps|all-small-caps|petite-caps|all-petite-caps|unicase|titling-caps",
    "lining-nums|oldstyle-nums|proportional-nums|tabular-nums",
    "diagonal-fractions|stacked-fractions",
    "ordinal|slashed-zero",
    "jis78|jis83|jis90|jis04|simplified|traditional",
    "full-width|proportional-width",
    "ruby"
  ].join("|") + ")$"),
  weight: /^(?:normal|bold|bolder|lighter|[1-9]00|inherit|initial|unset)$/,
  stretch: new RegExp("^(?:" + [
    "normal",
    "(?:(?:ultra|extra|semi)-)?(?:condensed|expanded)",
    "inherit|initial|unset"
  ].join("|") + ")$"),
  size: new RegExp("^(?:" + [
    "xx-small|x-small|small|medium|large|x-large|xx-large|larger|smaller",
    "[\\d.]+%|[\\d.]+[a-z]+",
    "inherit|initial|unset"
  ].join("|") + ")(?:/(?:normal|[\\d.]+(?:%|[a-z]+)?))?$")
};
function splitFont(name) {
  const parts = splitSpaces(this.styles[name]);
  const value = {
    style: "",
    variant: [],
    weight: "",
    stretch: "",
    size: "",
    family: "",
    "line-height": ""
  };
  for (const part of parts) {
    if (!value.family) {
      value.family = part;
    }
    for (const name2 of Object.keys(FONT)) {
      if ((Array.isArray(value[name2]) || value[name2] === "") && part.match(FONT[name2])) {
        if (value.family === part) {
          value.family = "";
        }
        if (name2 === "size") {
          const [size, height] = part.split(/\//);
          value[name2] = size;
          if (height) {
            value["line-height"] = height;
          }
        } else if (value.size === "") {
          if (Array.isArray(value[name2])) {
            value[name2].push(part);
          } else if (value[name2] === "") {
            value[name2] = part;
          }
        }
      }
    }
  }
  saveFontParts.call(this, name, value);
  delete this.styles[name];
}
function saveFontParts(name, value) {
  for (const child of Styles.connect[name].children) {
    const cname = this.childName(name, child);
    if (Array.isArray(value[child])) {
      const values = value[child];
      if (values.length) {
        this.styles[cname] = values.join(" ");
      }
    } else if (value[child] !== "") {
      this.styles[cname] = value[child];
    }
  }
}
function combineFont(_name) {
}
var Styles = class _Styles {
  constructor(cssText = "") {
    this.parse(cssText);
  }
  sanitizeValue(text) {
    const PATTERN = this.constructor.pattern;
    if (!text.match(PATTERN.sanitize)) {
      return text;
    }
    text = text.replace(PATTERN.value, "$1");
    const test = text.replace(/\\./g, "").replace(/(['"]).*?\1/g, "").replace(/[^'"]/g, "");
    if (test.length) {
      text += test.charAt(0);
    }
    return text;
  }
  get cssText() {
    var _a, _b;
    const styles = [];
    for (const name of Object.keys(this.styles)) {
      const parent = this.parentName(name);
      const cname = name.replace(/.*-/, "");
      const pname = this.childName(this.parentName(parent), cname);
      if (this.styles[name] && !this.styles[pname] && (!this.styles[parent] || !((_b = (_a = _Styles.connect[parent]) === null || _a === void 0 ? void 0 : _a.children) === null || _b === void 0 ? void 0 : _b.includes(cname)))) {
        styles.push(`${name}: ${this.styles[name]};`);
      }
    }
    return styles.join(" ");
  }
  get styleList() {
    return Object.assign({}, this.styles);
  }
  set(name, value) {
    name = this.normalizeName(name);
    this.setStyle(name, String(value));
    const connect = _Styles.connect[name];
    if (connect === null || connect === void 0 ? void 0 : connect.subPart) {
      connect.combine.call(this, name);
      return;
    }
    this.combineParent(name);
    if (name.match(/-.*-/)) {
      const pname = name.replace(/-.*-/, "-");
      combineSame.call(this, pname);
    }
  }
  combineParent(name) {
    var _a;
    while (name.match(/-/)) {
      const cname = name;
      name = this.parentName(name);
      const connect2 = _Styles.connect[name];
      if (!_Styles.connect[cname] && !((_a = connect2 === null || connect2 === void 0 ? void 0 : connect2.children) === null || _a === void 0 ? void 0 : _a.includes(cname.substring(name.length + 1)))) {
        break;
      }
      connect2.combine.call(this, name);
    }
    if (!this.styles[name]) {
      return;
    }
    const connect = _Styles.connect[name];
    for (const cname of (connect === null || connect === void 0 ? void 0 : connect.parts) || []) {
      delete this.styles[this.childName(name, cname)];
    }
  }
  get(name) {
    name = this.normalizeName(name);
    return Object.hasOwn(this.styles, name) ? this.styles[name] : "";
  }
  setStyle(name, value) {
    var _a;
    this.styles[name] = this.sanitizeValue(value);
    if ((_a = _Styles.connect[name]) === null || _a === void 0 ? void 0 : _a.children) {
      _Styles.connect[name].split.call(this, name);
    }
    if (value === "") {
      delete this.styles[name];
    }
  }
  combineChildren(name) {
    const parent = this.parentName(name);
    for (const child of _Styles.connect[name].children) {
      const cname = this.childName(parent, child);
      _Styles.connect[cname].combine.call(this, cname);
    }
  }
  parentName(name) {
    const parent = name.replace(/-[^-]*$/, "");
    return name === parent ? "" : parent;
  }
  childName(name, child) {
    var _a;
    if (child.match(/-/)) {
      return child;
    }
    if ((_a = _Styles.connect[name]) === null || _a === void 0 ? void 0 : _a.subPart) {
      child += name.replace(/.*-/, "-");
      name = this.parentName(name);
    }
    return name + "-" + child;
  }
  normalizeName(name) {
    return name.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase());
  }
  parse(cssText = "") {
    const PATTERN = this.constructor.pattern;
    this.styles = {};
    const parts = cssText.replace(/\n/g, " ").replace(PATTERN.comment, "").split(PATTERN.style);
    while (parts.length > 1) {
      const [space, name, value] = parts.splice(0, 3);
      if (space.match(/[^\s\n;]/))
        return;
      this.set(name, value);
    }
  }
};
Styles.pattern = {
  sanitize: /['";]/,
  value: /^((:?'(?:\\.|[^'])*(?:'|$)|"(?:\\.|[^"])*(?:"|$)|\n|\\.|[^'";])*?)[\s\n]*(?:;|$).*/,
  style: /([-a-z]+)[\s\n]*:[\s\n]*((?:'(?:\\.|[^'])*(?:'|$)|"(?:\\.|[^"])*(?:"|$)|\n|\\.|[^'";])*?)[\s\n]*(?:;|$)/g,
  comment: /\/\*[^]*?\*\//g
};
Styles.connect = {
  padding: {
    children: TRBL,
    split: splitTRBL,
    combine: combineTRBL
  },
  margin: {
    children: TRBL,
    split: splitTRBL,
    combine: combineTRBL
  },
  border: {
    children: TRBL,
    parts: WSC,
    split: splitSame,
    combine: combineSame
  },
  "border-top": {
    children: WSC,
    split: splitWSC,
    combine: combineWSC
  },
  "border-right": {
    children: WSC,
    split: splitWSC,
    combine: combineWSC
  },
  "border-bottom": {
    children: WSC,
    split: splitWSC,
    combine: combineWSC
  },
  "border-left": {
    children: WSC,
    split: splitWSC,
    combine: combineWSC
  },
  "border-width": {
    children: TRBL,
    split: splitTRBL,
    combine: combinePart,
    subPart: true
  },
  "border-style": {
    children: TRBL,
    split: splitTRBL,
    combine: combinePart,
    subPart: true
  },
  "border-color": {
    children: TRBL,
    split: splitTRBL,
    combine: combinePart,
    subPart: true
  },
  font: {
    children: [
      "style",
      "variant",
      "weight",
      "stretch",
      "line-height",
      "size",
      "family"
    ],
    split: splitFont,
    combine: combineFont
  }
};

// node_modules/@mathjax/src/mjs/input/tex/base/BaseItems.js
var StartItem = class extends BaseItem {
  constructor(factory, global) {
    super(factory);
    this.global = global;
  }
  get kind() {
    return "start";
  }
  get isOpen() {
    return true;
  }
  checkItem(item) {
    if (item.isKind("stop")) {
      let node = this.toMml();
      if (!this.global.isInner) {
        node = this.factory.configuration.tags.finalize(node, this.env);
      }
      return [[this.factory.create("mml", node)], true];
    }
    return super.checkItem(item);
  }
};
var StopItem = class extends BaseItem {
  get kind() {
    return "stop";
  }
  get isClose() {
    return true;
  }
};
var OpenItem = class extends BaseItem {
  get kind() {
    return "open";
  }
  get isOpen() {
    return true;
  }
  checkItem(item) {
    if (item.isKind("close")) {
      const mml = this.toMml();
      const node = this.create("node", "TeXAtom", [mml]);
      item.addLatexItem(node);
      return [[this.factory.create("mml", node)], true];
    }
    return super.checkItem(item);
  }
};
OpenItem.errors = Object.assign(Object.create(BaseItem.errors), {
  stop: ["ExtraOpenMissingClose", "Extra open brace or missing close brace"]
});
var CloseItem = class extends BaseItem {
  get kind() {
    return "close";
  }
  get isClose() {
    return true;
  }
};
var NullItem = class extends BaseItem {
  get kind() {
    return "null";
  }
};
var PrimeItem = class extends BaseItem {
  get kind() {
    return "prime";
  }
  checkItem(item) {
    const [top0, top1] = this.Peek(2);
    const isSup = (NodeUtil_default.isType(top0, "msubsup") || NodeUtil_default.isType(top0, "msup")) && !NodeUtil_default.getChildAt(top0, top0.sup);
    const isOver = (NodeUtil_default.isType(top0, "munderover") || NodeUtil_default.isType(top0, "mover")) && !NodeUtil_default.getChildAt(top0, top0.over) && !NodeUtil_default.getProperty(top0, "subsupOK");
    if (!isSup && !isOver) {
      const node = this.create("node", top0.getProperty("movesupsub") ? "mover" : "msup", [top0, top1]);
      return [[node, item], true];
    }
    const pos = isSup ? top0.sup : top0.over;
    NodeUtil_default.setChild(top0, pos, top1);
    return [[top0, item], true];
  }
};
var SubsupItem = class extends BaseItem {
  get kind() {
    return "subsup";
  }
  checkItem(item) {
    if (item.isKind("open") || item.isKind("left")) {
      return BaseItem.success;
    }
    const top = this.First;
    const position = this.getProperty("position");
    if (item.isKind("mml")) {
      if (this.getProperty("primes")) {
        if (position !== 2) {
          NodeUtil_default.setChild(top, 2, this.getProperty("primes"));
        } else {
          NodeUtil_default.setProperty(this.getProperty("primes"), "variantForm", true);
          const node = this.create("node", "mrow", [
            this.getProperty("primes"),
            item.First
          ]);
          item.First = node;
        }
      }
      NodeUtil_default.setChild(top, position, item.First);
      if (this.getProperty("movesupsub") != null) {
        NodeUtil_default.setProperty(top, "movesupsub", this.getProperty("movesupsub"));
      }
      const result = this.factory.create("mml", top);
      return [[result], true];
    }
    super.checkItem(item);
    const error = this.getErrors(["", "sub", "sup"][position]);
    throw new TexError_default(error[0], error[1], ...error.splice(2));
  }
};
SubsupItem.errors = Object.assign(Object.create(BaseItem.errors), {
  stop: ["MissingScript", "Missing superscript or subscript argument"],
  sup: ["MissingOpenForSup", "Missing open brace for superscript"],
  sub: ["MissingOpenForSub", "Missing open brace for subscript"]
});
var OverItem = class extends BaseItem {
  constructor(factory) {
    super(factory);
    this.setProperty("name", "\\over");
  }
  get kind() {
    return "over";
  }
  get isClose() {
    return true;
  }
  checkItem(item) {
    if (item.isKind("over")) {
      throw new TexError_default("AmbiguousUseOf", "Ambiguous use of %1", item.getName());
    }
    if (item.isClose) {
      let mml = this.create("node", "mfrac", [
        this.getProperty("num"),
        this.toMml(false)
      ]);
      if (this.getProperty("thickness") != null) {
        NodeUtil_default.setAttribute(mml, "linethickness", this.getProperty("thickness"));
      }
      if (this.getProperty("ldelim") || this.getProperty("rdelim")) {
        NodeUtil_default.setProperty(mml, "withDelims", true);
        mml = ParseUtil.fixedFence(this.factory.configuration, this.getProperty("ldelim"), mml, this.getProperty("rdelim"));
      }
      mml.attributes.set(TexConstant.Attr.LATEXITEM, this.getProperty("name"));
      return [[this.factory.create("mml", mml), item], true];
    }
    return super.checkItem(item);
  }
  toString() {
    return "over[" + this.getProperty("num") + " / " + this.nodes.join("; ") + "]";
  }
};
var LeftItem = class extends BaseItem {
  constructor(factory, delim) {
    super(factory);
    this.setProperty("delim", delim);
  }
  get kind() {
    return "left";
  }
  get isOpen() {
    return true;
  }
  checkItem(item) {
    if (item.isKind("right")) {
      const fenced = ParseUtil.fenced(this.factory.configuration, this.getProperty("delim"), this.toMml(), item.getProperty("delim"), "", item.getProperty("color"));
      const left = fenced.childNodes[0];
      const right = fenced.childNodes[fenced.childNodes.length - 1];
      const mrow = this.factory.create("mml", fenced);
      this.addLatexItem(left, "\\left");
      item.addLatexItem(right, "\\right");
      mrow.Peek()[0].attributes.set(TexConstant.Attr.LATEXITEM, "\\left" + item.startStr.slice(this.startI, item.stopI));
      return [[mrow], true];
    }
    if (item.isKind("middle")) {
      const def = { stretchy: true, symmetric: true };
      if (item.getProperty("color")) {
        def.mathcolor = item.getProperty("color");
      }
      const middle = this.create("token", "mo", def, item.getProperty("delim"));
      item.addLatexItem(middle, "\\middle");
      this.Push(this.create("node", "TeXAtom", [], { texClass: TEXCLASS.CLOSE }), middle, this.create("node", "TeXAtom", [], { texClass: TEXCLASS.OPEN }));
      this.env = {};
      return [[this], true];
    }
    return super.checkItem(item);
  }
};
LeftItem.errors = Object.assign(Object.create(BaseItem.errors), {
  stop: ["ExtraLeftMissingRight", "Extra \\left or missing \\right"]
});
var Middle = class extends BaseItem {
  constructor(factory, delim, color) {
    super(factory);
    this.setProperty("delim", delim);
    if (color) {
      this.setProperty("color", color);
    }
  }
  get kind() {
    return "middle";
  }
  get isClose() {
    return true;
  }
};
var RightItem = class extends BaseItem {
  constructor(factory, delim, color) {
    super(factory);
    this.setProperty("delim", delim);
    if (color) {
      this.setProperty("color", color);
    }
  }
  get kind() {
    return "right";
  }
  get isClose() {
    return true;
  }
};
var BreakItem = class extends BaseItem {
  get kind() {
    return "break";
  }
  constructor(factory, linebreak, insert2) {
    super(factory);
    this.setProperty("linebreak", linebreak);
    this.setProperty("insert", insert2);
  }
  checkItem(item) {
    var _a, _b;
    const linebreak = this.getProperty("linebreak");
    if (item.isKind("mml")) {
      const mml2 = item.First;
      if (mml2.isKind("mo")) {
        const style = ((_b = (_a = NodeUtil_default.getOp(mml2)) === null || _a === void 0 ? void 0 : _a[3]) === null || _b === void 0 ? void 0 : _b.linebreakstyle) || NodeUtil_default.getAttribute(mml2, "linebreakstyle");
        if (style !== "after") {
          NodeUtil_default.setAttribute(mml2, "linebreak", linebreak);
          return [[item], true];
        }
        if (!this.getProperty("insert")) {
          return [[item], true];
        }
      }
    }
    const mml = this.create("token", "mspace", { linebreak });
    return [[this.factory.create("mml", mml), item], true];
  }
};
var BeginItem = class extends BaseItem {
  get kind() {
    return "begin";
  }
  get isOpen() {
    return true;
  }
  checkItem(item) {
    if (item.isKind("end")) {
      if (item.getName() !== this.getName()) {
        throw new TexError_default("EnvBadEnd", "\\begin{%1} ended with \\end{%2}", this.getName(), item.getName());
      }
      const node = this.toMml();
      item.addLatexItem(node);
      return [[this.factory.create("mml", node)], true];
    }
    if (item.isKind("stop")) {
      throw new TexError_default("EnvMissingEnd", "Missing \\end{%1}", this.getName());
    }
    return super.checkItem(item);
  }
};
var EndItem = class extends BaseItem {
  get kind() {
    return "end";
  }
  get isClose() {
    return true;
  }
};
var StyleItem = class extends BaseItem {
  get kind() {
    return "style";
  }
  checkItem(item) {
    if (!item.isClose) {
      return super.checkItem(item);
    }
    const mml = this.create("node", "mstyle", this.nodes, this.getProperty("styles"));
    return [[this.factory.create("mml", mml), item], true];
  }
};
var PositionItem = class extends BaseItem {
  get kind() {
    return "position";
  }
  checkItem(item) {
    if (item.isClose) {
      throw new TexError_default("MissingBoxFor", "Missing box for %1", this.getName());
    }
    if (item.isFinal) {
      let mml = item.toMml();
      switch (this.getProperty("move")) {
        case "vertical":
          mml = this.create("node", "mpadded", [mml], {
            height: this.getProperty("dh"),
            depth: this.getProperty("dd"),
            voffset: this.getProperty("dh")
          });
          return [[this.factory.create("mml", mml)], true];
        case "horizontal":
          return [
            [
              this.factory.create("mml", this.getProperty("left")),
              item,
              this.factory.create("mml", this.getProperty("right"))
            ],
            true
          ];
      }
    }
    return super.checkItem(item);
  }
};
var CellItem = class extends BaseItem {
  get kind() {
    return "cell";
  }
  get isClose() {
    return true;
  }
};
var MmlItem = class extends BaseItem {
  get isFinal() {
    return true;
  }
  get kind() {
    return "mml";
  }
};
var FnItem = class extends BaseItem {
  get kind() {
    return "fn";
  }
  checkItem(item) {
    const top = this.First;
    if (top) {
      if (item.isOpen) {
        return BaseItem.success;
      }
      if (!item.isKind("fn")) {
        let mml = item.First;
        if (!item.isKind("mml") || !mml) {
          return [[top, item], true];
        }
        if (NodeUtil_default.isType(mml, "mstyle") && mml.childNodes.length && NodeUtil_default.isType(mml.childNodes[0].childNodes[0], "mspace") || NodeUtil_default.isType(mml, "mspace")) {
          return [[top, item], true];
        }
        if (NodeUtil_default.isEmbellished(mml)) {
          mml = NodeUtil_default.getCoreMO(mml);
        }
        const form = NodeUtil_default.getForm(mml);
        if (form != null && [0, 0, 1, 1, 0, 1, 1, 0, 0, 0][form[2]]) {
          return [[top, item], true];
        }
      }
      if (top.isKind("TeXAtom") && top.isEmpty) {
        return [[top, item], true];
      }
      const node = this.create("token", "mo", { texClass: TEXCLASS.NONE }, entities.ApplyFunction);
      return [[top, node, item], true];
    }
    return super.checkItem(item);
  }
};
var NotItem = class extends BaseItem {
  constructor() {
    super(...arguments);
    this.remap = MapHandler.getMap("not_remap");
  }
  get kind() {
    return "not";
  }
  checkItem(item) {
    let mml;
    let c;
    let textNode;
    if (item.isKind("open") || item.isKind("left")) {
      return BaseItem.success;
    }
    if (item.isKind("mml") && (NodeUtil_default.isType(item.First, "mo") || NodeUtil_default.isType(item.First, "mi") || NodeUtil_default.isType(item.First, "mtext"))) {
      mml = item.First;
      c = NodeUtil_default.getText(mml);
      if (c.length === 1 && !NodeUtil_default.getProperty(mml, "movesupsub") && NodeUtil_default.getChildren(mml).length === 1) {
        if (this.remap.contains(c)) {
          textNode = this.create("text", this.remap.lookup(c).char);
          NodeUtil_default.setChild(mml, 0, textNode);
        } else {
          textNode = this.create("text", "\u0338");
          NodeUtil_default.appendChildren(mml, [textNode]);
        }
        return [[item], true];
      }
    }
    textNode = this.create("text", "\u29F8");
    const mtextNode = this.create("node", "mtext", [], {}, textNode);
    const paddedNode = this.create("node", "mpadded", [mtextNode], {
      width: 0
    });
    mml = this.create("node", "TeXAtom", [paddedNode], {
      texClass: TEXCLASS.REL
    });
    return [[mml, item], true];
  }
};
var NonscriptItem = class extends BaseItem {
  get kind() {
    return "nonscript";
  }
  checkItem(item) {
    if (item.isKind("mml") && item.Size() === 1) {
      let mml = item.First;
      if (mml.isKind("mstyle") && mml.notParent) {
        mml = NodeUtil_default.getChildren(NodeUtil_default.getChildren(mml)[0])[0];
      }
      if (mml.isKind("mspace")) {
        if (mml !== item.First) {
          const mrow = this.create("node", "mrow", [item.Pop()]);
          item.Push(mrow);
        }
        this.factory.configuration.addNode("nonscript", item.First);
      }
    }
    return [[item], true];
  }
};
var DotsItem = class extends BaseItem {
  get kind() {
    return "dots";
  }
  checkItem(item) {
    if (item.isKind("open") || item.isKind("left")) {
      return BaseItem.success;
    }
    let dots = this.getProperty("ldots");
    const top = item.First;
    if (item.isKind("mml") && NodeUtil_default.isEmbellished(top)) {
      const tclass = NodeUtil_default.getTexClass(NodeUtil_default.getCoreMO(top));
      if (tclass === TEXCLASS.BIN || tclass === TEXCLASS.REL) {
        dots = this.getProperty("cdots");
      }
    }
    return [[dots, item], true];
  }
};
var ArrayItem = class extends BaseItem {
  constructor() {
    super(...arguments);
    this.table = [];
    this.row = [];
    this.frame = [];
    this.hfill = [];
    this.arraydef = {};
    this.cstart = [];
    this.cend = [];
    this.cextra = [];
    this.atEnd = false;
    this.ralign = [];
    this.breakAlign = {
      cell: "",
      row: "",
      table: ""
    };
    this.templateSubs = 0;
  }
  get kind() {
    return "array";
  }
  get isOpen() {
    return true;
  }
  get copyEnv() {
    return false;
  }
  checkItem(item) {
    if (item.isClose && !item.isKind("over")) {
      if (item.getProperty("isEntry")) {
        this.EndEntry();
        this.clearEnv();
        this.StartEntry();
        return BaseItem.fail;
      }
      if (item.getProperty("isCR")) {
        this.EndEntry();
        this.EndRow();
        this.clearEnv();
        this.StartEntry();
        return BaseItem.fail;
      }
      this.EndTable();
      this.clearEnv();
      const newItem = this.factory.create("mml", this.createMml());
      if (this.getProperty("requireClose")) {
        if (item.isKind("close")) {
          return [[newItem], true];
        }
        throw new TexError_default("MissingCloseBrace", "Missing close brace");
      }
      return [[newItem, item], true];
    }
    return super.checkItem(item);
  }
  createMml() {
    const scriptlevel = this.arraydef["scriptlevel"];
    delete this.arraydef["scriptlevel"];
    let mml = this.create("node", "mtable", this.table, this.arraydef);
    if (scriptlevel) {
      mml.setProperty("smallmatrix", true);
    }
    if (this.breakAlign.table) {
      NodeUtil_default.setAttribute(mml, "data-break-align", this.breakAlign.table);
    }
    if (this.getProperty("arrayPadding")) {
      NodeUtil_default.setAttribute(mml, "data-frame-styles", "");
      NodeUtil_default.setAttribute(mml, "framespacing", this.getProperty("arrayPadding"));
    }
    mml = this.handleFrame(mml);
    if (scriptlevel !== void 0) {
      mml = this.create("node", "mstyle", [mml], { scriptlevel });
    }
    if (this.getProperty("open") || this.getProperty("close")) {
      mml = ParseUtil.fenced(this.factory.configuration, this.getProperty("open"), mml, this.getProperty("close"));
    }
    return mml;
  }
  handleFrame(mml) {
    if (!this.frame.length)
      return mml;
    const sides = new Map(this.frame);
    const fstyle = this.frame.reduce((fstyle2, [, style]) => style === fstyle2 ? style : "", this.frame[0][1]);
    if (fstyle) {
      if (this.frame.length === 4) {
        NodeUtil_default.setAttribute(mml, "frame", fstyle);
        NodeUtil_default.removeAttribute(mml, "data-frame-styles");
        return mml;
      }
      if (fstyle === "solid") {
        NodeUtil_default.setAttribute(mml, "data-frame-styles", "");
        mml = this.create("node", "menclose", [mml], {
          notation: Array.from(sides.keys()).join(" "),
          "data-padding": 0
        });
        return mml;
      }
    }
    const styles = TRBL.map((side) => sides.get(side) || "none").join(" ");
    NodeUtil_default.setAttribute(mml, "data-frame-styles", styles);
    return mml;
  }
  StartEntry() {
    const n = this.row.length;
    let start = this.cstart[n];
    let end = this.cend[n];
    const ralign = this.ralign[n];
    const cextra = this.cextra;
    if (!start && !end && !ralign && !cextra[n] && !cextra[n + 1])
      return;
    let [prefix, entry, term, found] = this.getEntry();
    if (cextra[n] && (!this.atEnd || cextra[n + 1])) {
      start += "&";
    }
    if (term !== "&") {
      found = !!entry.trim() || !!(n || term && term.substring(0, 4) !== "\\end");
      if (cextra[n + 1] && !cextra[n]) {
        end = (end || "") + "&";
        this.atEnd = true;
      }
    }
    if (!found && !prefix)
      return;
    const parser = this.parser;
    if (found) {
      if (start) {
        entry = ParseUtil.addArgs(parser, start, entry);
      }
      if (end) {
        entry = ParseUtil.addArgs(parser, entry, end);
      }
      if (ralign) {
        entry = "\\text{" + entry.trim() + "}";
      }
      if (start || end || ralign) {
        if (++this.templateSubs > parser.configuration.options.maxTemplateSubtitutions) {
          throw new TexError_default("MaxTemplateSubs", "Maximum template substitutions exceeded; is there an invalid use of \\\\ in the template?");
        }
      }
    }
    if (prefix) {
      entry = ParseUtil.addArgs(parser, prefix, entry);
    }
    parser.string = ParseUtil.addArgs(parser, entry, parser.string);
    parser.i = 0;
  }
  getEntry() {
    const parser = this.parser;
    const pattern = /^([^]*?)([&{}]|\\\\|\\(?:begin|end)\s*\{array\}|\\cr|\\)/;
    let braces = 0;
    let envs = 0;
    let i = parser.i;
    let match;
    const fail = ["", "", "", false];
    while ((match = parser.string.slice(i).match(pattern)) !== null) {
      i += match[0].length;
      switch (match[2]) {
        case "\\":
          i++;
          break;
        case "{":
          braces++;
          break;
        case "}":
          if (!braces)
            return fail;
          braces--;
          break;
        case "\\begin{array}":
          if (!braces) {
            envs++;
          }
          break;
        case "\\end{array}":
          if (!braces && envs) {
            envs--;
            break;
          }
        default: {
          if (braces || envs)
            continue;
          i -= match[2].length;
          let entry = parser.string.slice(parser.i, i).trim();
          const prefix = entry.match(/^(?:\s*\\(?:h(?:dash)?line|hfil{1,3}|rowcolor\s*\{.*?\}))+/);
          if (prefix) {
            entry = entry.slice(prefix[0].length);
          }
          parser.string = parser.string.slice(i);
          parser.i = 0;
          return [(prefix === null || prefix === void 0 ? void 0 : prefix[0]) || "", entry, match[2], true];
        }
      }
    }
    return fail;
  }
  EndEntry() {
    const mtd = this.create("node", "mtd", this.nodes);
    if (this.hfill.length) {
      if (this.hfill[0] === 0) {
        NodeUtil_default.setAttribute(mtd, "columnalign", "right");
      }
      if (this.hfill[this.hfill.length - 1] === this.Size()) {
        NodeUtil_default.setAttribute(mtd, "columnalign", NodeUtil_default.getAttribute(mtd, "columnalign") ? "center" : "left");
      }
    }
    const ralign = this.ralign[this.row.length];
    if (ralign) {
      const [valign, cwidth, calign] = ralign;
      const box = this.create("node", "mpadded", mtd.childNodes[0].childNodes, {
        width: cwidth,
        "data-overflow": "auto",
        "data-align": calign,
        "data-vertical-align": valign
      });
      box.setProperty("vbox", valign);
      mtd.childNodes[0].childNodes = [];
      mtd.appendChild(box);
    } else if (this.breakAlign.cell) {
      NodeUtil_default.setAttribute(mtd, "data-vertical-align", this.breakAlign.cell);
    }
    this.breakAlign.cell = "";
    this.row.push(mtd);
    this.Clear();
    this.hfill = [];
  }
  EndRow() {
    let type = "mtr";
    if (this.getProperty("isNumbered") && this.row.length === 3) {
      this.row.unshift(this.row.pop());
      type = "mlabeledtr";
    } else if (this.getProperty("isLabeled")) {
      type = "mlabeledtr";
      this.setProperty("isLabeled", false);
    }
    const node = this.create("node", type, this.row);
    if (this.breakAlign.row) {
      NodeUtil_default.setAttribute(node, "data-break-align", this.breakAlign.row);
      this.breakAlign.row = "";
    }
    this.addLatexItem(node);
    this.table.push(node);
    this.row = [];
    this.atEnd = false;
  }
  EndTable() {
    if (this.Size() || this.row.length) {
      this.EndEntry();
      this.EndRow();
    }
    this.checkLines();
  }
  checkLines() {
    if (this.arraydef.rowlines) {
      const lines2 = this.arraydef.rowlines.split(/ /);
      if (lines2.length === this.table.length) {
        this.frame.push(["bottom", lines2.pop()]);
        if (lines2.length) {
          this.arraydef.rowlines = lines2.join(" ");
        } else {
          delete this.arraydef.rowlines;
        }
      } else if (lines2.length < this.table.length - 1) {
        this.arraydef.rowlines += " none";
      }
    }
    if (this.getProperty("rowspacing")) {
      const rows = this.arraydef.rowspacing.split(/ /);
      while (rows.length < this.table.length) {
        rows.push(this.getProperty("rowspacing") + "em");
      }
      this.arraydef.rowspacing = rows.join(" ");
    }
  }
  addRowSpacing(spacing) {
    if (this.arraydef["rowspacing"]) {
      const rows = this.arraydef["rowspacing"].split(/ /);
      if (!this.getProperty("rowspacing")) {
        const dimem = UnitUtil.dimen2em(rows[0]);
        this.setProperty("rowspacing", dimem);
      }
      const rowspacing = this.getProperty("rowspacing");
      while (rows.length < this.table.length) {
        rows.push(UnitUtil.em(rowspacing));
      }
      rows[this.table.length - 1] = UnitUtil.em(Math.max(0, rowspacing + UnitUtil.dimen2em(spacing)));
      this.arraydef["rowspacing"] = rows.join(" ");
    }
  }
};
var EqnArrayItem = class extends ArrayItem {
  constructor(factory, ...args) {
    super(factory);
    this.maxrow = 0;
    this.factory.configuration.tags.start(args[0], args[2], args[1]);
  }
  get kind() {
    return "eqnarray";
  }
  EndEntry() {
    const calign = this.arraydef.columnalign.split(/ /);
    const align = this.row.length && calign.length ? calign[this.row.length % calign.length] : "right";
    if (align !== "right") {
      ParseUtil.fixInitialMO(this.factory.configuration, this.nodes);
    }
    super.EndEntry();
  }
  EndRow() {
    if (this.row.length > this.maxrow) {
      this.maxrow = this.row.length;
    }
    const tag = this.factory.configuration.tags.getTag();
    if (tag) {
      this.row = [tag].concat(this.row);
      this.setProperty("isLabeled", true);
    }
    this.factory.configuration.tags.clearTag();
    super.EndRow();
  }
  EndTable() {
    super.EndTable();
    this.factory.configuration.tags.end();
    this.extendArray("columnalign", this.maxrow);
    this.extendArray("columnwidth", this.maxrow);
    this.extendArray("columnspacing", this.maxrow - 1);
    this.extendArray("data-break-align", this.maxrow);
    this.addIndentshift();
  }
  extendArray(name, max) {
    if (!this.arraydef[name])
      return;
    const repeat = this.arraydef[name].split(/ /);
    const columns = [...repeat];
    if (columns.length > 1) {
      while (columns.length < max) {
        columns.push(...repeat);
      }
      this.arraydef[name] = columns.slice(0, max).join(" ");
    }
  }
  addIndentshift() {
    const align = this.arraydef.columnalign.split(/ /);
    let prev = "";
    for (const i of align.keys()) {
      if (align[i] === "left" && i > 0) {
        const indentshift = prev === "center" ? ".7em" : "2em";
        for (const row of this.table) {
          const cell = row.childNodes[row.isKind("mlabeledtr") ? i + 1 : i];
          if (cell) {
            const mstyle = this.create("node", "mstyle", cell.childNodes[0].childNodes, { indentshift });
            cell.childNodes[0].childNodes = [];
            cell.appendChild(mstyle);
          }
        }
      }
      prev = align[i];
    }
  }
};
var MstyleItem = class extends BeginItem {
  get kind() {
    return "mstyle";
  }
  constructor(factory, attr, name) {
    super(factory);
    this.attrList = attr;
    this.setProperty("name", name);
  }
  checkItem(item) {
    if (item.isKind("end") && item.getName() === this.getName()) {
      const mml = this.create("node", "mstyle", [this.toMml()], this.attrList);
      return [[mml], true];
    }
    return super.checkItem(item);
  }
};
var EquationItem = class extends BaseItem {
  constructor(factory, ...args) {
    super(factory);
    this.factory.configuration.tags.start("equation", true, args[0]);
  }
  get kind() {
    return "equation";
  }
  get isOpen() {
    return true;
  }
  checkItem(item) {
    if (item.isKind("end")) {
      const mml = this.toMml();
      const tag = this.factory.configuration.tags.getTag();
      this.factory.configuration.tags.end();
      return [
        [tag ? this.factory.configuration.tags.enTag(mml, tag) : mml, item],
        true
      ];
    }
    if (item.isKind("stop")) {
      throw new TexError_default("EnvMissingEnd", "Missing \\end{%1}", this.getName());
    }
    return super.checkItem(item);
  }
};

// node_modules/@mathjax/src/mjs/util/lengths.js
var BIGDIMEN = 1e6;
var UNITS = {
  px: 1,
  "in": 96,
  cm: 96 / 2.54,
  mm: 96 / 25.4
};
var RELUNITS = {
  em: 1,
  ex: 0.431,
  pt: 1 / 10,
  pc: 12 / 10,
  mu: 1 / 18
};
var MATHSPACE = {
  veryverythinmathspace: 1 / 18,
  verythinmathspace: 2 / 18,
  thinmathspace: 3 / 18,
  mediummathspace: 4 / 18,
  thickmathspace: 5 / 18,
  verythickmathspace: 6 / 18,
  veryverythickmathspace: 7 / 18,
  negativeveryverythinmathspace: -1 / 18,
  negativeverythinmathspace: -2 / 18,
  negativethinmathspace: -3 / 18,
  negativemediummathspace: -4 / 18,
  negativethickmathspace: -5 / 18,
  negativeverythickmathspace: -6 / 18,
  negativeveryverythickmathspace: -7 / 18,
  thin: 0.04,
  medium: 0.06,
  thick: 0.1,
  normal: 1,
  big: 2,
  small: 1 / Math.sqrt(2),
  infinity: BIGDIMEN
};
function em(m) {
  if (Math.abs(m) < 1e-3)
    return "0";
  return m.toFixed(3).replace(/\.?0+$/, "") + "em";
}

// node_modules/@mathjax/src/mjs/input/tex/base/BaseMethods.js
var P_HEIGHT = 1.2 / 0.85;
var MmlTokenAllow = {
  fontfamily: 1,
  fontsize: 1,
  fontweight: 1,
  fontstyle: 1,
  color: 1,
  background: 1,
  id: 1,
  class: 1,
  href: 1,
  style: 1
};
function splitAlignArray(align, n = Infinity) {
  const list = align.replace(/\s+/g, "").split("").map((s) => {
    const name = { t: "top", b: "bottom", m: "middle", c: "center" }[s];
    if (!name) {
      throw new TexError_default("BadBreakAlign", "Invalid alignment character: %1", s);
    }
    return name;
  });
  if (list.length > n) {
    throw new TexError_default("TooManyAligns", "Too many alignment characters: %1", align);
  }
  return n === 1 ? list[0] : list.join(" ");
}
function parseRoot(parser, n) {
  const env = parser.stack.env;
  const inRoot = env["inRoot"];
  env["inRoot"] = true;
  const newParser = new TexParser(n, env, parser.configuration);
  let node = newParser.mml();
  const global = newParser.stack.global;
  if (global["leftRoot"] || global["upRoot"]) {
    const def = {};
    if (global["leftRoot"]) {
      def["width"] = global["leftRoot"];
    }
    if (global["upRoot"]) {
      def["voffset"] = global["upRoot"];
      def["height"] = global["upRoot"];
    }
    node = parser.create("node", "mpadded", [node], def);
  }
  env["inRoot"] = inRoot;
  return node;
}
var BaseMethods = {
  Open(parser, _c) {
    parser.Push(parser.itemFactory.create("open"));
  },
  Close(parser, _c) {
    parser.Push(parser.itemFactory.create("close"));
  },
  Bar(parser, c) {
    const mo = parser.create("token", "mo", { stretchy: false, texClass: TEXCLASS.ORD }, c);
    mo.setProperty("keep-attrs", "stretchy");
    parser.Push(mo);
  },
  Tilde(parser, _c) {
    parser.Push(parser.create("token", "mtext", {}, entities.nbsp));
  },
  Space(_parser, _c) {
  },
  Superscript(parser, _c) {
    if (parser.GetNext().match(/\d/)) {
      parser.string = parser.string.substring(0, parser.i + 1) + " " + parser.string.substring(parser.i + 1);
    }
    let primes;
    let base;
    const top = parser.stack.Top();
    if (top.isKind("prime")) {
      [base, primes] = top.Peek(2);
      parser.stack.Pop();
    } else {
      base = parser.stack.Prev();
      if (!base) {
        base = parser.create("token", "mi", {}, "");
      }
    }
    const movesupsub = NodeUtil_default.getProperty(base, "movesupsub");
    let position = NodeUtil_default.isType(base, "msubsup") ? base.sup : base.over;
    if (NodeUtil_default.isType(base, "msubsup") && !NodeUtil_default.isType(base, "msup") && NodeUtil_default.getChildAt(base, base.sup) || NodeUtil_default.isType(base, "munderover") && !NodeUtil_default.isType(base, "mover") && NodeUtil_default.getChildAt(base, base.over) && !NodeUtil_default.getProperty(base, "subsupOK")) {
      throw new TexError_default("DoubleExponent", "Double exponent: use braces to clarify");
    }
    if (!NodeUtil_default.isType(base, "msubsup") || NodeUtil_default.isType(base, "msup")) {
      if (movesupsub) {
        if (!NodeUtil_default.isType(base, "munderover") || NodeUtil_default.isType(base, "mover") || NodeUtil_default.getChildAt(base, base.over)) {
          base = parser.create("node", "munderover", [base], {
            movesupsub: true
          });
        }
        position = base.over;
      } else {
        base = parser.create("node", "msubsup", [base]);
        position = base.sup;
      }
    }
    parser.Push(parser.itemFactory.create("subsup", base).setProperties({
      position,
      primes,
      movesupsub
    }));
  },
  Subscript(parser, _c) {
    if (parser.GetNext().match(/\d/)) {
      parser.string = parser.string.substring(0, parser.i + 1) + " " + parser.string.substring(parser.i + 1);
    }
    let primes, base;
    const top = parser.stack.Top();
    if (top.isKind("prime")) {
      [base, primes] = top.Peek(2);
      parser.stack.Pop();
    } else {
      base = parser.stack.Prev();
      if (!base) {
        base = parser.create("token", "mi", {}, "");
      }
    }
    const movesupsub = NodeUtil_default.getProperty(base, "movesupsub");
    let position = NodeUtil_default.isType(base, "msubsup") ? base.sub : base.under;
    if (NodeUtil_default.isType(base, "msubsup") && !NodeUtil_default.isType(base, "msup") && NodeUtil_default.getChildAt(base, base.sub) || NodeUtil_default.isType(base, "munderover") && !NodeUtil_default.isType(base, "mover") && NodeUtil_default.getChildAt(base, base.under) && !NodeUtil_default.getProperty(base, "subsupOK")) {
      throw new TexError_default("DoubleSubscripts", "Double subscripts: use braces to clarify");
    }
    if (!NodeUtil_default.isType(base, "msubsup") || NodeUtil_default.isType(base, "msup")) {
      if (movesupsub) {
        if (!NodeUtil_default.isType(base, "munderover") || NodeUtil_default.isType(base, "mover") || NodeUtil_default.getChildAt(base, base.under)) {
          base = parser.create("node", "munderover", [base], {
            movesupsub: true
          });
        }
        position = base.under;
      } else {
        base = parser.create("node", "msubsup", [base]);
        position = base.sub;
      }
    }
    parser.Push(parser.itemFactory.create("subsup", base).setProperties({
      position,
      primes,
      movesupsub
    }));
  },
  Prime(parser, c) {
    let base = parser.stack.Prev();
    if (!base) {
      base = parser.create("token", "mi");
    }
    if (NodeUtil_default.isType(base, "msubsup") && !NodeUtil_default.isType(base, "msup") && NodeUtil_default.getChildAt(base, base.sup) || NodeUtil_default.isType(base, "munderover") && !NodeUtil_default.isType(base, "mover") && NodeUtil_default.getChildAt(base, base.over) && !NodeUtil_default.getProperty(base, "subsupOK")) {
      throw new TexError_default("DoubleExponentPrime", "Prime causes double exponent: use braces to clarify");
    }
    let sup = "";
    parser.i--;
    do {
      sup += entities.prime;
      parser.i++;
      c = parser.GetNext();
    } while (c === "'" || c === entities.rsquo);
    sup = ["", "\u2032", "\u2033", "\u2034", "\u2057"][sup.length] || sup;
    const node = parser.create("token", "mo", { variantForm: true }, sup);
    parser.Push(parser.itemFactory.create("prime", base, node));
  },
  Comment(parser, _c) {
    while (parser.i < parser.string.length && parser.string.charAt(parser.i) !== "\n") {
      parser.i++;
    }
  },
  Hash(_parser, _c) {
    throw new TexError_default("CantUseHash1", "You can't use 'macro parameter character #' in math mode");
  },
  MathFont(parser, name, variant, italic = "") {
    const text = parser.GetArgument(name);
    const mml = new TexParser(text, Object.assign(Object.assign({ multiLetterIdentifiers: parser.options.identifierPattern }, parser.stack.env), { font: variant, italicFont: italic, noAutoOP: true }), parser.configuration).mml();
    parser.Push(parser.create("node", "TeXAtom", [mml]));
  },
  SetFont(parser, _name, font) {
    parser.stack.env["font"] = font;
    parser.Push(parser.itemFactory.create("null"));
  },
  SetStyle(parser, _name, texStyle, style, level) {
    parser.stack.env["style"] = texStyle;
    parser.stack.env["level"] = level;
    parser.Push(parser.itemFactory.create("style").setProperty("styles", { displaystyle: style, scriptlevel: level }));
  },
  SetSize(parser, _name, size) {
    parser.stack.env["size"] = size;
    parser.Push(parser.itemFactory.create("style").setProperty("styles", { mathsize: em(size) }));
  },
  Spacer(parser, _name, space) {
    const node = parser.create("node", "mspace", [], { width: em(space) });
    const style = parser.create("node", "mstyle", [node], { scriptlevel: 0 });
    parser.Push(style);
  },
  DiscretionaryTimes(parser, _name) {
    parser.Push(parser.create("token", "mo", { linebreakmultchar: "\xD7" }, "\u2062"));
  },
  AllowBreak(parser, _name) {
    parser.Push(parser.create("token", "mspace"));
  },
  Break(parser, _name) {
    parser.Push(parser.create("token", "mspace", {
      linebreak: TexConstant.LineBreak.NEWLINE
    }));
  },
  Linebreak(parser, _name, linebreak) {
    let insert2 = true;
    const prev = parser.stack.Prev(true);
    if (prev && prev.isKind("mo")) {
      const style = NodeUtil_default.getMoAttribute(prev, "linebreakstyle");
      if (style !== TexConstant.LineBreakStyle.BEFORE) {
        prev.attributes.set("linebreak", linebreak);
        insert2 = false;
      }
    }
    parser.Push(parser.itemFactory.create("break", linebreak, insert2));
  },
  LeftRight(parser, name) {
    const first = name.substring(1);
    parser.Push(parser.itemFactory.create(first, parser.GetDelimiter(name), parser.stack.env.color));
  },
  NamedFn(parser, name, id) {
    if (!id) {
      id = name.substring(1);
    }
    const mml = parser.create("token", "mi", { texClass: TEXCLASS.OP }, id);
    parser.Push(parser.itemFactory.create("fn", mml));
  },
  NamedOp(parser, name, id) {
    if (!id) {
      id = name.substring(1);
    }
    id = id.replace(/&thinsp;/, "\u2006");
    const mml = parser.create("token", "mo", {
      movablelimits: true,
      movesupsub: true,
      form: TexConstant.Form.PREFIX,
      texClass: TEXCLASS.OP
    }, id);
    parser.Push(mml);
  },
  Limits(parser, _name, limits) {
    let op = parser.stack.Prev(true);
    if (!op || NodeUtil_default.getTexClass(NodeUtil_default.getCoreMO(op)) !== TEXCLASS.OP && NodeUtil_default.getProperty(op, "movesupsub") == null) {
      throw new TexError_default("MisplacedLimits", "%1 is allowed only on operators", parser.currentCS);
    }
    const top = parser.stack.Top();
    let node;
    if (NodeUtil_default.isType(op, "munderover") && !limits) {
      node = parser.create("node", "msubsup");
      NodeUtil_default.copyChildren(op, node);
      op = top.First = node;
    } else if (NodeUtil_default.isType(op, "msubsup") && limits) {
      node = parser.create("node", "munderover");
      NodeUtil_default.copyChildren(op, node);
      op = top.First = node;
    }
    NodeUtil_default.setProperty(op, "movesupsub", limits ? true : false);
    NodeUtil_default.setProperties(NodeUtil_default.getCoreMO(op), { movablelimits: false });
    if ((NodeUtil_default.isType(op, "mo") ? NodeUtil_default.getMoAttribute(op, "movableLimits") : NodeUtil_default.getAttribute(op, "movablelimits")) || NodeUtil_default.getProperty(op, "movablelimits")) {
      NodeUtil_default.setProperties(op, { movablelimits: false });
    }
  },
  Over(parser, name, open, close) {
    const mml = parser.itemFactory.create("over").setProperty("name", parser.currentCS);
    if (open || close) {
      mml.setProperty("ldelim", open);
      mml.setProperty("rdelim", close);
    } else if (name.match(/withdelims$/)) {
      mml.setProperty("ldelim", parser.GetDelimiter(name));
      mml.setProperty("rdelim", parser.GetDelimiter(name));
    }
    if (name.match(/^\\above/)) {
      mml.setProperty("thickness", parser.GetDimen(name));
    } else if (name.match(/^\\atop/) || open || close) {
      mml.setProperty("thickness", 0);
    }
    parser.Push(mml);
  },
  Frac(parser, name) {
    const num = parser.ParseArg(name);
    const den = parser.ParseArg(name);
    const node = parser.create("node", "mfrac", [num, den]);
    parser.Push(node);
  },
  Sqrt(parser, name) {
    const n = parser.GetBrackets(name);
    let arg = parser.GetArgument(name);
    if (arg === "\\frac") {
      arg += "{" + parser.GetArgument(arg) + "}{" + parser.GetArgument(arg) + "}";
    }
    let mml = new TexParser(arg, parser.stack.env, parser.configuration).mml();
    if (!n) {
      mml = parser.create("node", "msqrt", [mml]);
    } else {
      mml = parser.create("node", "mroot", [mml, parseRoot(parser, n)]);
    }
    parser.Push(mml);
  },
  Root(parser, name) {
    const n = parser.GetUpTo(name, "\\of");
    const arg = parser.ParseArg(name);
    const node = parser.create("node", "mroot", [arg, parseRoot(parser, n)]);
    parser.Push(node);
  },
  MoveRoot(parser, name, id) {
    if (!parser.stack.env["inRoot"]) {
      throw new TexError_default("MisplacedMoveRoot", "%1 can appear only within a root", parser.currentCS);
    }
    if (parser.stack.global[id]) {
      throw new TexError_default("MultipleMoveRoot", "Multiple use of %1", parser.currentCS);
    }
    let n = parser.GetArgument(name);
    if (!n.match(/-?[0-9]+/)) {
      throw new TexError_default("IntegerArg", "The argument to %1 must be an integer", parser.currentCS);
    }
    n = parseInt(n, 10) / 15 + "em";
    if (n.substring(0, 1) !== "-") {
      n = "+" + n;
    }
    parser.stack.global[id] = n;
  },
  Accent(parser, name, accent, stretchy) {
    const c = parser.ParseArg(name);
    const def = Object.assign(Object.assign({}, ParseUtil.getFontDef(parser)), { accent: true, mathaccent: stretchy === void 0 ? true : stretchy });
    const entity = NodeUtil_default.createEntity(accent);
    const mml = parser.create("token", "mo", def, entity);
    NodeUtil_default.setAttribute(mml, "stretchy", stretchy ? true : false);
    const mo = NodeUtil_default.isEmbellished(c) ? NodeUtil_default.getCoreMO(c) : c;
    if (NodeUtil_default.isType(mo, "mo") || NodeUtil_default.getProperty(mo, "movablelimits")) {
      NodeUtil_default.setProperties(mo, { movablelimits: false });
    }
    const muoNode = parser.create("node", "munderover");
    NodeUtil_default.setChild(muoNode, 0, c);
    NodeUtil_default.setChild(muoNode, 1, null);
    NodeUtil_default.setChild(muoNode, 2, mml);
    const texAtom = parser.create("node", "TeXAtom", [muoNode]);
    parser.Push(texAtom);
  },
  UnderOver(parser, name, c, stack) {
    const entity = NodeUtil_default.createEntity(c);
    const mo = parser.create("token", "mo", { stretchy: true, accent: true }, entity);
    if (entity.match(MmlMo.mathaccentsWithWidth)) {
      mo.setProperty("mathaccent", false);
    }
    const pos = name.charAt(1) === "o" ? "over" : "under";
    const base = parser.ParseArg(name);
    parser.Push(ParseUtil.underOver(parser, base, mo, pos, stack));
  },
  Overset(parser, name) {
    const top = parser.ParseArg(name);
    const base = parser.ParseArg(name);
    const topMo = top.coreMO();
    const accent = topMo.isKind("mo") && NodeUtil_default.getMoAttribute(topMo, "accent") === true;
    ParseUtil.checkMovableLimits(base);
    const node = parser.create("node", "mover", [base, top], { accent });
    parser.Push(node);
  },
  Underset(parser, name) {
    const bot = parser.ParseArg(name);
    const base = parser.ParseArg(name);
    const botMo = bot.coreMO();
    const accentunder = botMo.isKind("mo") && NodeUtil_default.getMoAttribute(botMo, "accent") === true;
    ParseUtil.checkMovableLimits(base);
    const node = parser.create("node", "munder", [base, bot], { accentunder });
    parser.Push(node);
  },
  Overunderset(parser, name) {
    const top = parser.ParseArg(name);
    const bot = parser.ParseArg(name);
    const base = parser.ParseArg(name);
    const topMo = top.coreMO();
    const botMo = bot.coreMO();
    const accent = topMo.isKind("mo") && NodeUtil_default.getMoAttribute(topMo, "accent") === true;
    const accentunder = botMo.isKind("mo") && NodeUtil_default.getMoAttribute(botMo, "accent") === true;
    ParseUtil.checkMovableLimits(base);
    const node = parser.create("node", "munderover", [base, bot, top], {
      accent,
      accentunder
    });
    parser.Push(node);
  },
  TeXAtom(parser, name, mclass) {
    const def = { texClass: mclass };
    let mml;
    let node;
    if (mclass === TEXCLASS.OP) {
      def["movesupsub"] = def["movablelimits"] = true;
      const arg = parser.GetArgument(name);
      const match = arg.match(/^\s*\\rm\s+([a-zA-Z0-9 ]+)$/);
      if (match) {
        def["mathvariant"] = TexConstant.Variant.NORMAL;
        node = parser.create("token", "mi", def, match[1]);
      } else {
        const parsed = new TexParser(arg, parser.stack.env, parser.configuration).mml();
        node = parser.create("node", "TeXAtom", [parsed], def);
      }
      mml = parser.itemFactory.create("fn", node);
    } else {
      mml = parser.create("node", "TeXAtom", [parser.ParseArg(name)], def);
    }
    parser.Push(mml);
  },
  VBox(parser, name, align) {
    const arg = new TexParser(parser.GetArgument(name), parser.stack.env, parser.configuration);
    const def = {
      "data-vertical-align": align,
      texClass: TEXCLASS.ORD
    };
    if (arg.stack.env.hsize) {
      def.width = arg.stack.env.hsize;
      def["data-overflow"] = "linebreak";
    }
    const mml = parser.create("node", "mpadded", [arg.mml()], def);
    mml.setProperty("vbox", align);
    parser.Push(mml);
  },
  Hsize(parser, name) {
    if (parser.GetNext() === "=") {
      parser.i++;
    }
    parser.stack.env.hsize = parser.GetDimen(name);
    parser.Push(parser.itemFactory.create("null"));
  },
  ParBox(parser, name) {
    const c = parser.GetBrackets(name, "c");
    const width = parser.GetDimen(name);
    const text = ParseUtil.internalMath(parser, parser.GetArgument(name));
    const align = splitAlignArray(c, 1);
    const mml = parser.create("node", "mpadded", text, {
      width,
      "data-overflow": "linebreak",
      "data-vertical-align": align
    });
    mml.setProperty("vbox", align);
    parser.Push(mml);
  },
  BreakAlign(parser, name) {
    const top = parser.stack.Top();
    if (!(top instanceof ArrayItem)) {
      throw new TexError_default("BreakNotInArray", "%1 must be used in an alignment environment", parser.currentCS);
    }
    const type = parser.GetArgument(name).trim();
    switch (type) {
      case "c":
        if (top.First) {
          throw new TexError_default("BreakFirstInEntry", "%1 must be at the beginning of an alignment entry", parser.currentCS + "{c}");
        }
        top.breakAlign.cell = splitAlignArray(parser.GetArgument(name), 1);
        break;
      case "r":
        if (top.row.length || top.First) {
          throw new TexError_default("BreakFirstInRow", "%1 must be at the beginning of an alignment row", parser.currentCS + "{r}");
        }
        top.breakAlign.row = splitAlignArray(parser.GetArgument(name));
        break;
      case "t":
        if (top.table.length || top.row.length || top.First) {
          throw new TexError_default("BreakFirstInTable", "%1 must be at the beginning of an alignment", parser.currentCS + "{t}");
        }
        top.breakAlign.table = splitAlignArray(parser.GetArgument(name));
        break;
      default:
        throw new TexError_default("BreakType", "First argument to %1 must be one of c, r, or t", parser.currentCS);
    }
  },
  MmlToken(parser, name) {
    const kind = parser.GetArgument(name);
    let attr = parser.GetBrackets(name, "").replace(/^\s+/, "");
    const text = parser.GetArgument(name);
    const def = {};
    const keep = [];
    let node;
    try {
      node = parser.create("node", kind);
    } catch (_e) {
      node = null;
    }
    if (!node || !node.isToken) {
      throw new TexError_default("NotMathMLToken", "%1 is not a token element", kind);
    }
    while (attr !== "") {
      const match = attr.match(/^([a-z]+)\s*=\s*('[^'\n]*'|"[^"\n]*"|[^ ,\n]*)[\s\n]*,?[\s\n]*/i);
      if (!match) {
        throw new TexError_default("InvalidMathMLAttr", "Invalid MathML attribute: %1", attr.split(/[\s\n=]/)[0]);
      }
      if (!node.attributes.hasDefault(match[1]) && !MmlTokenAllow[match[1]]) {
        throw new TexError_default("UnknownAttrForElement", "%1 is not a recognized attribute for %2", match[1], kind);
      }
      let value = ParseUtil.mmlFilterAttribute(parser, match[1], match[2].replace(/^(['"])(.*)\1$/, "$2"));
      if (value) {
        if (value.toLowerCase() === "true") {
          value = true;
        } else if (value.toLowerCase() === "false") {
          value = false;
        }
        def[match[1]] = value;
        keep.push(match[1]);
      }
      attr = attr.substring(match[0].length);
    }
    if (keep.length) {
      node.setProperty("keep-attrs", keep.join(" "));
    }
    const textNode = parser.create("text", replaceUnicode(text));
    node.appendChild(textNode);
    NodeUtil_default.setProperties(node, def);
    parser.Push(node);
  },
  Strut(parser, _name) {
    const row = parser.create("node", "mrow");
    const padded = parser.create("node", "mpadded", [row], {
      height: "8.6pt",
      depth: "3pt",
      width: 0
    });
    parser.Push(padded);
  },
  Phantom(parser, name, v, h) {
    let box = parser.create("node", "mphantom", [parser.ParseArg(name)]);
    if (v || h) {
      box = parser.create("node", "mpadded", [box]);
      if (h) {
        NodeUtil_default.setAttribute(box, "height", 0);
        NodeUtil_default.setAttribute(box, "depth", 0);
      }
      if (v) {
        NodeUtil_default.setAttribute(box, "width", 0);
      }
    }
    const atom = parser.create("node", "TeXAtom", [box]);
    parser.Push(atom);
  },
  Smash(parser, name) {
    const bt = UnitUtil.trimSpaces(parser.GetBrackets(name, ""));
    const smash = parser.create("node", "mpadded", [parser.ParseArg(name)]);
    switch (bt) {
      case "b":
        NodeUtil_default.setAttribute(smash, "depth", 0);
        break;
      case "t":
        NodeUtil_default.setAttribute(smash, "height", 0);
        break;
      default:
        NodeUtil_default.setAttribute(smash, "height", 0);
        NodeUtil_default.setAttribute(smash, "depth", 0);
    }
    const atom = parser.create("node", "TeXAtom", [smash]);
    parser.Push(atom);
  },
  Lap(parser, name) {
    const mml = parser.create("node", "mpadded", [parser.ParseArg(name)], {
      width: 0
    });
    if (name === "\\llap") {
      NodeUtil_default.setAttribute(mml, "lspace", "-1width");
    }
    const atom = parser.create("node", "TeXAtom", [mml]);
    parser.Push(atom);
  },
  RaiseLower(parser, name) {
    let h = parser.GetDimen(name);
    const item = parser.itemFactory.create("position").setProperties({ name: parser.currentCS, move: "vertical" });
    if (h.charAt(0) === "-") {
      h = h.slice(1);
      name = name.substring(1) === "raise" ? "\\lower" : "\\raise";
    }
    if (name === "\\lower") {
      item.setProperty("dh", "-" + h);
      item.setProperty("dd", "+" + h);
    } else {
      item.setProperty("dh", "+" + h);
      item.setProperty("dd", "-" + h);
    }
    parser.Push(item);
  },
  MoveLeftRight(parser, name) {
    let h = parser.GetDimen(name);
    let nh = h.charAt(0) === "-" ? h.slice(1) : "-" + h;
    if (name === "\\moveleft") {
      const tmp = h;
      h = nh;
      nh = tmp;
    }
    parser.Push(parser.itemFactory.create("position").setProperties({
      name: parser.currentCS,
      move: "horizontal",
      left: parser.create("node", "mspace", [], { width: h }),
      right: parser.create("node", "mspace", [], { width: nh })
    }));
  },
  Hskip(parser, name, nobreak = false) {
    const node = parser.create("node", "mspace", [], {
      width: parser.GetDimen(name)
    });
    if (nobreak) {
      NodeUtil_default.setAttribute(node, "linebreak", "nobreak");
    }
    parser.Push(node);
  },
  Nonscript(parser, _name) {
    parser.Push(parser.itemFactory.create("nonscript"));
  },
  Rule(parser, name, style) {
    const w = parser.GetDimen(name), h = parser.GetDimen(name), d = parser.GetDimen(name);
    const def = { width: w, height: h, depth: d };
    if (style !== "blank") {
      def["mathbackground"] = parser.stack.env["color"] || "black";
    }
    const node = parser.create("node", "mspace", [], def);
    parser.Push(node);
  },
  rule(parser, name) {
    const v = parser.GetBrackets(name), w = parser.GetDimen(name), h = parser.GetDimen(name);
    let mml = parser.create("node", "mspace", [], {
      width: w,
      height: h,
      mathbackground: parser.stack.env["color"] || "black"
    });
    if (v) {
      mml = parser.create("node", "mpadded", [mml], { voffset: v });
      if (v.match(/^-/)) {
        NodeUtil_default.setAttribute(mml, "height", v);
        NodeUtil_default.setAttribute(mml, "depth", "+" + v.substring(1));
      } else {
        NodeUtil_default.setAttribute(mml, "height", "+" + v);
      }
    }
    parser.Push(mml);
  },
  MakeBig(parser, name, mclass, size) {
    size *= P_HEIGHT;
    const sizeStr = String(size).replace(/(\.\d\d\d).+/, "$1") + "em";
    const delim = parser.GetDelimiter(name, true);
    const mo = parser.create("token", "mo", {
      minsize: sizeStr,
      maxsize: sizeStr,
      fence: true,
      stretchy: true,
      symmetric: true
    }, delim);
    const node = parser.create("node", "TeXAtom", [mo], { texClass: mclass });
    parser.Push(node);
  },
  BuildRel(parser, name) {
    const top = parser.ParseUpTo(name, "\\over");
    const bot = parser.ParseArg(name);
    const node = parser.create("node", "munderover");
    NodeUtil_default.setChild(node, 0, bot);
    NodeUtil_default.setChild(node, 1, null);
    NodeUtil_default.setChild(node, 2, top);
    const atom = parser.create("node", "TeXAtom", [node], {
      texClass: TEXCLASS.REL
    });
    parser.Push(atom);
  },
  HBox(parser, name, style, font) {
    parser.PushAll(ParseUtil.internalMath(parser, parser.GetArgument(name), style, font));
  },
  FBox(parser, name) {
    const internal = ParseUtil.internalMath(parser, parser.GetArgument(name));
    const node = parser.create("node", "menclose", internal, {
      notation: "box"
    });
    parser.Push(node);
  },
  FrameBox(parser, name) {
    const width = parser.GetBrackets(name);
    const pos = parser.GetBrackets(name) || "c";
    let mml = ParseUtil.internalMath(parser, parser.GetArgument(name));
    if (width) {
      mml = [
        parser.create("node", "mpadded", mml, {
          width,
          "data-align": lookup(pos, { l: "left", r: "right" }, "center")
        })
      ];
    }
    const node = parser.create("node", "TeXAtom", [parser.create("node", "menclose", mml, { notation: "box" })], { texClass: TEXCLASS.ORD });
    parser.Push(node);
  },
  MakeBox(parser, name) {
    const width = parser.GetBrackets(name);
    const pos = parser.GetBrackets(name, "c");
    const mml = parser.create("node", "mpadded", ParseUtil.internalMath(parser, parser.GetArgument(name)));
    if (width) {
      NodeUtil_default.setAttribute(mml, "width", width);
    }
    const align = lookup(pos.toLowerCase(), { c: "center", r: "right" }, "");
    if (align) {
      NodeUtil_default.setAttribute(mml, "data-align", align);
    }
    if (pos.toLowerCase() !== pos) {
      NodeUtil_default.setAttribute(mml, "data-overflow", "linebreak");
    }
    parser.Push(mml);
  },
  Not(parser, _name) {
    parser.Push(parser.itemFactory.create("not"));
  },
  Dots(parser, _name) {
    const ldotsEntity = NodeUtil_default.createEntity("2026");
    const cdotsEntity = NodeUtil_default.createEntity("22EF");
    const ldots = parser.create("token", "mo", { stretchy: false }, ldotsEntity);
    const cdots = parser.create("token", "mo", { stretchy: false }, cdotsEntity);
    parser.Push(parser.itemFactory.create("dots").setProperties({
      ldots,
      cdots
    }));
  },
  Matrix(parser, _name, open, close, align, spacing, vspacing, style, cases, numbered) {
    const c = parser.GetNext();
    if (c === "") {
      throw new TexError_default("MissingArgFor", "Missing argument for %1", parser.currentCS);
    }
    if (c === "{") {
      parser.i++;
    } else {
      parser.string = c + "}" + parser.string.slice(parser.i + 1);
      parser.i = 0;
    }
    const array = parser.itemFactory.create("array").setProperty("requireClose", true);
    if (open || !align) {
      array.setProperty("arrayPadding", ".2em .125em");
    }
    array.arraydef = {
      rowspacing: vspacing || "4pt",
      columnspacing: spacing || "1em"
    };
    if (cases) {
      array.setProperty("isCases", true);
    }
    if (numbered) {
      array.setProperty("isNumbered", true);
      array.arraydef.side = numbered;
    }
    if (open || close) {
      array.setProperty("open", open);
      array.setProperty("close", close);
    }
    if (style === "D") {
      array.arraydef.displaystyle = true;
    }
    if (align != null) {
      array.arraydef.columnalign = align;
    }
    parser.Push(array);
  },
  Entry(parser, name) {
    parser.Push(parser.itemFactory.create("cell").setProperties({ isEntry: true, name }));
    const top = parser.stack.Top();
    const env = top.getProperty("casesEnv");
    const cases = top.getProperty("isCases");
    if (!cases && !env)
      return;
    const str = parser.string;
    let braces = 0;
    let close = -1;
    let i = parser.i;
    let m = str.length;
    const end = env ? new RegExp(`^\\\\end\\s*\\{${env.replace(/\*/, "\\*")}\\}`) : null;
    while (i < m) {
      const c = str.charAt(i);
      if (c === "{") {
        braces++;
        i++;
      } else if (c === "}") {
        if (braces === 0) {
          m = 0;
        } else {
          braces--;
          if (braces === 0 && close < 0) {
            close = i - parser.i;
          }
          i++;
        }
      } else if (c === "&" && braces === 0) {
        throw new TexError_default("ExtraAlignTab", "Extra alignment tab in \\cases text");
      } else if (c === "\\") {
        const rest = str.substring(i);
        if (rest.match(/^((\\cr)[^a-zA-Z]|\\\\)/) || end && rest.match(end)) {
          m = 0;
        } else {
          i += 2;
        }
      } else {
        i++;
      }
    }
    const text = str.substring(parser.i, i);
    if (!text.match(/^\s*\\text[^a-zA-Z]/) || close !== text.replace(/\s+$/, "").length - 1) {
      const internal = ParseUtil.internalMath(parser, UnitUtil.trimSpaces(text), 0);
      parser.PushAll(internal);
      parser.i = i;
    }
  },
  Cr(parser, name) {
    parser.Push(parser.itemFactory.create("cell").setProperties({ isCR: true, name }));
  },
  CrLaTeX(parser, name, nobrackets = false) {
    let n;
    if (!nobrackets) {
      if (parser.string.charAt(parser.i) === "*") {
        parser.i++;
      }
      if (parser.string.charAt(parser.i) === "[") {
        const dim = parser.GetBrackets(name, "");
        const [value, unit] = UnitUtil.matchDimen(dim);
        if (dim && !value) {
          throw new TexError_default("BracketMustBeDimension", "Bracket argument to %1 must be a dimension", parser.currentCS);
        }
        n = value + unit;
      }
    }
    parser.Push(parser.itemFactory.create("cell").setProperties({ isCR: true, name, linebreak: true }));
    const top = parser.stack.Top();
    let node;
    if (top instanceof ArrayItem) {
      if (n) {
        top.addRowSpacing(n);
      }
    } else {
      node = parser.create("node", "mspace", [], {
        linebreak: TexConstant.LineBreak.NEWLINE
      });
      if (n) {
        NodeUtil_default.setAttribute(node, "data-lineleading", n);
      }
      parser.Push(node);
    }
  },
  HLine(parser, _name, style) {
    if (style == null) {
      style = "solid";
    }
    const top = parser.stack.Top();
    if (!(top instanceof ArrayItem) || top.Size()) {
      throw new TexError_default("Misplaced", "Misplaced %1", parser.currentCS);
    }
    if (!top.table.length) {
      top.frame.push(["top", style]);
    } else {
      const lines2 = top.arraydef["rowlines"] ? top.arraydef["rowlines"].split(/ /) : [];
      while (lines2.length < top.table.length) {
        lines2.push("none");
      }
      lines2[top.table.length - 1] = style;
      top.arraydef["rowlines"] = lines2.join(" ");
    }
  },
  HFill(parser, _name) {
    const top = parser.stack.Top();
    if (top instanceof ArrayItem) {
      top.hfill.push(top.Size());
    } else {
      throw new TexError_default("UnsupportedHFill", "Unsupported use of %1", parser.currentCS);
    }
  },
  NewColumnType(parser, name) {
    const c = parser.GetArgument(name);
    const n = parser.GetBrackets(name, "0");
    const macro = parser.GetArgument(name);
    if (c.length !== 1) {
      throw new TexError_default("BadColumnName", "Column specifier must be exactly one character: %1", c);
    }
    if (!n.match(/^\d+$/)) {
      throw new TexError_default("PositiveIntegerArg", "Argument to %1 must be a positive integer", n);
    }
    const cparser = parser.configuration.columnParser;
    cparser.columnHandler[c] = (state) => cparser.macroColumn(state, macro, parseInt(n));
    parser.Push(parser.itemFactory.create("null"));
  },
  BeginEnd(parser, name) {
    const env = parser.GetArgument(name);
    if (env.match(/\\/)) {
      throw new TexError_default("InvalidEnv", "Invalid environment name '%1'", env);
    }
    const macro = parser.configuration.handlers.get(HandlerType.ENVIRONMENT).lookup(env);
    if (macro && name === "\\end") {
      if (!macro.args[0]) {
        const mml = parser.itemFactory.create("end").setProperty("name", env);
        parser.Push(mml);
        return;
      }
      parser.stack.env["closing"] = env;
    }
    ParseUtil.checkMaxMacros(parser, false);
    parser.parse(HandlerType.ENVIRONMENT, [parser, env]);
  },
  Array(parser, begin, open, close, align, spacing, vspacing, style, raggedHeight) {
    if (!align) {
      align = parser.GetArgument("\\begin{" + begin.getName() + "}");
    }
    const array = parser.itemFactory.create("array");
    if (begin.getName() === "array") {
      array.setProperty("arrayPadding", ".5em .125em");
    }
    array.parser = parser;
    array.arraydef = {
      columnspacing: spacing || "1em",
      rowspacing: vspacing || "4pt"
    };
    parser.configuration.columnParser.process(parser, align, array);
    if (open) {
      array.setProperty("open", parser.convertDelimiter(open));
    }
    if (close) {
      array.setProperty("close", parser.convertDelimiter(close));
    }
    if ((style || "").charAt(1) === "'") {
      array.arraydef["data-cramped"] = true;
      style = style.charAt(0);
    }
    if (style === "D") {
      array.arraydef["displaystyle"] = true;
    } else if (style) {
      array.arraydef["displaystyle"] = false;
    }
    array.arraydef["scriptlevel"] = style === "S" ? 1 : 0;
    if (raggedHeight) {
      array.arraydef["useHeight"] = false;
    }
    parser.Push(begin);
    array.StartEntry();
    return array;
  },
  AlignedArray(parser, begin, style = "") {
    const align = parser.GetBrackets("\\begin{" + begin.getName() + "}");
    const item = BaseMethods.Array(parser, begin, null, null, null, null, null, style);
    return ParseUtil.setArrayAlign(item, align);
  },
  IndentAlign(parser, begin) {
    const name = `\\begin{${begin.getName()}}`;
    const first = parser.GetBrackets(name, "");
    const shift = parser.GetBrackets(name, "");
    const last = parser.GetBrackets(name, "");
    if (first && !UnitUtil.matchDimen(first)[0] || shift && !UnitUtil.matchDimen(shift)[0] || last && !UnitUtil.matchDimen(last)[0]) {
      throw new TexError_default("BracketMustBeDimension", "Bracket argument to %1 must be a dimension", name);
    }
    const lcr = parser.GetArgument(name);
    if (lcr && !lcr.match(/^([lcr]{1,3})?$/)) {
      throw new TexError_default("BadAlignment", "Alignment must be one to three copies of l, c, or r");
    }
    const align = [...lcr].map((c) => ({ l: "left", c: "center", r: "right" })[c]);
    if (align.length === 1) {
      align.push(align[0]);
    }
    const attr = {};
    for (const [name2, value] of [
      ["indentshiftfirst", first],
      ["indentshift", shift || first],
      ["indentshiftlast", last],
      ["indentalignfirst", align[0]],
      ["indentalign", align[1]],
      ["indentalignlast", align[2]]
    ]) {
      if (value) {
        attr[name2] = value;
      }
    }
    parser.Push(parser.itemFactory.create("mstyle", attr, begin.getName()));
  },
  Equation(parser, begin, numbered, display = true) {
    parser.configuration.mathItem.display = display;
    parser.stack.env.display = display;
    ParseUtil.checkEqnEnv(parser);
    parser.Push(begin);
    return parser.itemFactory.create("equation", numbered).setProperty("name", begin.getName());
  },
  EqnArray(parser, begin, numbered, taggable, align, balign, spacing) {
    const name = begin.getName();
    const isGather = name === "gather" || name === "gather*";
    if (taggable) {
      ParseUtil.checkEqnEnv(parser, !isGather);
    }
    parser.Push(begin);
    align = align.replace(/[^clr]/g, "").split("").join(" ");
    align = align.replace(/l/g, "left").replace(/r/g, "right").replace(/c/g, "center");
    balign = splitAlignArray(balign);
    const newItem = parser.itemFactory.create("eqnarray", name, numbered, taggable, parser.stack.global);
    newItem.arraydef = {
      displaystyle: true,
      columnalign: align,
      columnspacing: spacing || "1em",
      rowspacing: "3pt",
      "data-break-align": balign,
      side: parser.options["tagSide"],
      minlabelspacing: parser.options["tagIndent"]
    };
    if (isGather) {
      newItem.setProperty("nestable", true);
    }
    return newItem;
  },
  HandleNoTag(parser, _name) {
    parser.tags.notag();
  },
  HandleLabel(parser, name) {
    const label = parser.GetArgument(name);
    if (label === "") {
      return;
    }
    if (parser.tags.label) {
      throw new TexError_default("MultipleCommand", "Multiple %1", parser.currentCS);
    }
    parser.tags.label = label;
    if (!parser.tags.refUpdate) {
      if ((parser.tags.allLabels[label] || parser.tags.labels[label]) && !parser.options["ignoreDuplicateLabels"]) {
        throw new TexError_default("MultipleLabel", "Label '%1' multiply defined", label);
      }
      parser.tags.labels[label] = new Label();
    }
  },
  HandleRef(parser, name, eqref) {
    const label = parser.GetArgument(name);
    let ref = parser.tags.allLabels[label] || parser.tags.labels[label];
    if (!ref) {
      if (!parser.tags.refUpdate) {
        parser.tags.redo = true;
      }
      ref = new Label();
    }
    let tag = ref.tag;
    if (eqref) {
      tag = parser.tags.formatRef(tag);
    }
    const node = parser.create("node", "mrow", ParseUtil.internalMath(parser, Array.isArray(tag) ? tag.join("") : tag), {
      href: parser.tags.formatUrl(ref.id, parser.options.baseURL),
      class: "MathJax_ref"
    });
    parser.Push(node);
  },
  Macro(parser, name, macro, argcount, def) {
    if (argcount) {
      const args = [];
      if (def != null) {
        const optional = parser.GetBrackets(name);
        args.push(optional == null ? def : optional);
      }
      for (let i = args.length; i < argcount; i++) {
        args.push(parser.GetArgument(name));
      }
      macro = ParseUtil.substituteArgs(parser, args, macro);
    }
    parser.string = ParseUtil.addArgs(parser, macro, parser.string.slice(parser.i));
    parser.i = 0;
    ParseUtil.checkMaxMacros(parser);
  },
  MathChoice(parser, name) {
    const D = parser.ParseArg(name);
    const T = parser.ParseArg(name);
    const S = parser.ParseArg(name);
    const SS = parser.ParseArg(name);
    parser.Push(parser.create("node", "MathChoice", [D, T, S, SS]));
  }
};
var BaseMethods_default = BaseMethods;

// node_modules/@mathjax/src/mjs/input/tex/ParseMethods.js
var MATHVARIANT2 = TexConstant.Variant;
var ParseMethods = {
  variable(parser, c) {
    var _a;
    const def = ParseUtil.getFontDef(parser);
    const env = parser.stack.env;
    if (env.multiLetterIdentifiers && env.font !== "") {
      c = ((_a = parser.string.substring(parser.i - 1).match(env.multiLetterIdentifiers)) === null || _a === void 0 ? void 0 : _a[0]) || c;
      parser.i += c.length - 1;
      if (def.mathvariant === MATHVARIANT2.NORMAL && env.noAutoOP && c.length > 1) {
        def.autoOP = false;
      }
    }
    if (!def.mathvariant && ParseUtil.isLatinOrGreekChar(c)) {
      const variant = parser.configuration.mathStyle(c);
      if (variant) {
        def.mathvariant = variant;
      }
    }
    const node = parser.create("token", "mi", def, c);
    parser.Push(node);
  },
  digit(parser, _c) {
    const pattern = parser.configuration.options["numberPattern"];
    const n = parser.string.slice(parser.i - 1).match(pattern);
    if (!n) {
      return false;
    }
    const def = ParseUtil.getFontDef(parser);
    const mml = parser.create("token", "mn", def, n[0].replace(/[{}]/g, ""));
    parser.i += n[0].length - 1;
    parser.Push(mml);
    return true;
  },
  controlSequence(parser, _c) {
    const name = parser.GetCS();
    parser.parse(HandlerType.MACRO, [parser, name]);
  },
  lcGreek(parser, mchar) {
    const def = {
      mathvariant: parser.configuration.mathStyle(mchar.char) || MATHVARIANT2.ITALIC
    };
    const node = parser.create("token", "mi", def, mchar.char);
    parser.Push(node);
  },
  ucGreek(parser, mchar) {
    const def = {
      mathvariant: parser.stack.env["font"] || parser.configuration.mathStyle(mchar.char, true) || MATHVARIANT2.NORMAL
    };
    const node = parser.create("token", "mi", def, mchar.char);
    parser.Push(node);
  },
  mathchar0mi(parser, mchar) {
    const def = mchar.attributes || { mathvariant: MATHVARIANT2.ITALIC };
    const node = parser.create("token", "mi", def, mchar.char);
    parser.Push(node);
  },
  mathchar0mo(parser, mchar) {
    const def = mchar.attributes || {};
    def["stretchy"] = false;
    const node = parser.create("token", "mo", def, mchar.char);
    NodeUtil_default.setProperty(node, "fixStretchy", true);
    parser.configuration.addNode("fixStretchy", node);
    parser.Push(node);
  },
  mathchar7(parser, mchar) {
    const def = mchar.attributes || { mathvariant: MATHVARIANT2.NORMAL };
    if (parser.stack.env["font"]) {
      def["mathvariant"] = parser.stack.env["font"];
    }
    const node = parser.create("token", "mi", def, mchar.char);
    parser.Push(node);
  },
  delimiter(parser, delim) {
    let def = delim.attributes || {};
    def = Object.assign({ fence: false, stretchy: false }, def);
    const node = parser.create("token", "mo", def, delim.char);
    if (delim.char === "|") {
      node.setProperty("keep-attrs", "stretchy");
    }
    parser.Push(node);
  },
  environment(parser, env, func, args) {
    const mml = parser.itemFactory.create("begin").setProperty("name", env);
    parser.Push(func(parser, mml, ...args.slice(1)));
  }
};
var ParseMethods_default = ParseMethods;

// node_modules/@mathjax/src/mjs/input/tex/base/BaseMappings.js
var THICKMATHSPACE = em(MATHSPACE.thickmathspace);
var VARIANT = TexConstant.Variant;
new RegExpMap("letter", ParseMethods_default.variable, /[a-z]/i);
new RegExpMap("digit", ParseMethods_default.digit, /[0-9.,]/);
new RegExpMap("command", ParseMethods_default.controlSequence, /^\\/);
new MacroMap("special", {
  "{": BaseMethods_default.Open,
  "}": BaseMethods_default.Close,
  "~": BaseMethods_default.Tilde,
  "^": BaseMethods_default.Superscript,
  _: BaseMethods_default.Subscript,
  "|": BaseMethods_default.Bar,
  " ": BaseMethods_default.Space,
  "	": BaseMethods_default.Space,
  "\r": BaseMethods_default.Space,
  "\n": BaseMethods_default.Space,
  "'": BaseMethods_default.Prime,
  "%": BaseMethods_default.Comment,
  "&": BaseMethods_default.Entry,
  "#": BaseMethods_default.Hash,
  "\xA0": BaseMethods_default.Space,
  "\u2019": BaseMethods_default.Prime
});
new CharacterMap("lcGreek", ParseMethods_default.lcGreek, {
  alpha: "\u03B1",
  beta: "\u03B2",
  gamma: "\u03B3",
  delta: "\u03B4",
  epsilon: "\u03F5",
  zeta: "\u03B6",
  eta: "\u03B7",
  theta: "\u03B8",
  iota: "\u03B9",
  kappa: "\u03BA",
  lambda: "\u03BB",
  mu: "\u03BC",
  nu: "\u03BD",
  xi: "\u03BE",
  omicron: "\u03BF",
  pi: "\u03C0",
  rho: "\u03C1",
  sigma: "\u03C3",
  tau: "\u03C4",
  upsilon: "\u03C5",
  phi: "\u03D5",
  chi: "\u03C7",
  psi: "\u03C8",
  omega: "\u03C9",
  varepsilon: "\u03B5",
  vartheta: "\u03D1",
  varpi: "\u03D6",
  varrho: "\u03F1",
  varsigma: "\u03C2",
  varphi: "\u03C6"
});
new CharacterMap("ucGreek", ParseMethods_default.ucGreek, {
  Gamma: "\u0393",
  Delta: "\u0394",
  Theta: "\u0398",
  Lambda: "\u039B",
  Xi: "\u039E",
  Pi: "\u03A0",
  Sigma: "\u03A3",
  Upsilon: "\u03A5",
  Phi: "\u03A6",
  Psi: "\u03A8",
  Omega: "\u03A9"
});
new CharacterMap("mathchar0mi", ParseMethods_default.mathchar0mi, {
  AA: "\u212B",
  S: ["\xA7", { mathvariant: VARIANT.NORMAL }],
  aleph: ["\u2135", { mathvariant: VARIANT.NORMAL }],
  hbar: ["\u210F", { variantForm: true }],
  imath: "\u0131",
  jmath: "\u0237",
  ell: "\u2113",
  wp: ["\u2118", { mathvariant: VARIANT.NORMAL }],
  Re: ["\u211C", { mathvariant: VARIANT.NORMAL }],
  Im: ["\u2111", { mathvariant: VARIANT.NORMAL }],
  partial: ["\u2202", { mathvariant: VARIANT.ITALIC }],
  infty: ["\u221E", { mathvariant: VARIANT.NORMAL }],
  prime: ["\u2032", { variantForm: true }],
  emptyset: ["\u2205", { mathvariant: VARIANT.NORMAL }],
  nabla: ["\u2207", { mathvariant: VARIANT.NORMAL }],
  top: ["\u22A4", { mathvariant: VARIANT.NORMAL }],
  bot: ["\u22A5", { mathvariant: VARIANT.NORMAL }],
  angle: ["\u2220", { mathvariant: VARIANT.NORMAL }],
  triangle: ["\u25B3", { mathvariant: VARIANT.NORMAL }],
  backslash: ["\\", { mathvariant: VARIANT.NORMAL }],
  forall: ["\u2200", { mathvariant: VARIANT.NORMAL }],
  exists: ["\u2203", { mathvariant: VARIANT.NORMAL }],
  neg: ["\xAC", { mathvariant: VARIANT.NORMAL }],
  lnot: ["\xAC", { mathvariant: VARIANT.NORMAL }],
  flat: ["\u266D", { mathvariant: VARIANT.NORMAL }],
  natural: ["\u266E", { mathvariant: VARIANT.NORMAL }],
  sharp: ["\u266F", { mathvariant: VARIANT.NORMAL }],
  clubsuit: ["\u2663", { mathvariant: VARIANT.NORMAL }],
  diamondsuit: ["\u2662", { mathvariant: VARIANT.NORMAL }],
  heartsuit: ["\u2661", { mathvariant: VARIANT.NORMAL }],
  spadesuit: ["\u2660", { mathvariant: VARIANT.NORMAL }]
});
new CharacterMap("mathchar0mo", ParseMethods_default.mathchar0mo, {
  surd: ["\u221A", { symmetric: true }],
  coprod: ["\u2210", { movesupsub: true }],
  bigvee: ["\u22C1", { movesupsub: true }],
  bigwedge: ["\u22C0", { movesupsub: true }],
  biguplus: ["\u2A04", { movesupsub: true }],
  bigcap: ["\u22C2", { movesupsub: true }],
  bigcup: ["\u22C3", { movesupsub: true }],
  int: "\u222B",
  intop: ["\u222B", { movesupsub: true, movablelimits: true }],
  iint: "\u222C",
  iiint: "\u222D",
  prod: ["\u220F", { movesupsub: true }],
  sum: ["\u2211", { movesupsub: true }],
  bigotimes: ["\u2A02", { movesupsub: true }],
  bigoplus: ["\u2A01", { movesupsub: true }],
  bigodot: ["\u2A00", { movesupsub: true }],
  oint: "\u222E",
  ointop: ["\u222E", { movesupsub: true, movablelimits: true }],
  oiint: "\u222F",
  oiiint: "\u2230",
  bigsqcup: ["\u2A06", { movesupsub: true }],
  smallint: ["\u222B", { largeop: false }],
  triangleleft: "\u25C3",
  triangleright: "\u25B9",
  bigtriangleup: "\u25B3",
  bigtriangledown: "\u25BD",
  wedge: "\u2227",
  land: "\u2227",
  vee: "\u2228",
  lor: "\u2228",
  cap: "\u2229",
  cup: "\u222A",
  ddagger: "\u2021",
  dagger: "\u2020",
  sqcap: "\u2293",
  sqcup: "\u2294",
  uplus: "\u228E",
  amalg: "\u2A3F",
  diamond: "\u22C4",
  bullet: "\u2219",
  wr: "\u2240",
  div: "\xF7",
  odot: ["\u2299", { largeop: false }],
  oslash: ["\u2298", { largeop: false }],
  otimes: ["\u2297", { largeop: false }],
  ominus: ["\u2296", { largeop: false }],
  oplus: ["\u2295", { largeop: false }],
  mp: "\u2213",
  pm: "\xB1",
  circ: "\u2218",
  bigcirc: "\u25EF",
  setminus: "\u2216",
  cdot: "\u22C5",
  ast: "\u2217",
  times: "\xD7",
  star: "\u22C6",
  propto: "\u221D",
  sqsubseteq: "\u2291",
  sqsupseteq: "\u2292",
  parallel: "\u2225",
  mid: "\u2223",
  dashv: "\u22A3",
  vdash: "\u22A2",
  leq: "\u2264",
  le: "\u2264",
  geq: "\u2265",
  ge: "\u2265",
  lt: "<",
  gt: ">",
  succ: "\u227B",
  prec: "\u227A",
  approx: "\u2248",
  succeq: "\u2AB0",
  preceq: "\u2AAF",
  supset: "\u2283",
  subset: "\u2282",
  supseteq: "\u2287",
  subseteq: "\u2286",
  in: "\u2208",
  ni: "\u220B",
  notin: "\u2209",
  owns: "\u220B",
  gg: "\u226B",
  ll: "\u226A",
  sim: "\u223C",
  simeq: "\u2243",
  perp: "\u27C2",
  equiv: "\u2261",
  asymp: "\u224D",
  smile: "\u2323",
  frown: "\u2322",
  ne: "\u2260",
  neq: "\u2260",
  cong: "\u2245",
  doteq: "\u2250",
  bowtie: "\u22C8",
  models: "\u22A7",
  notChar: "\u29F8",
  Leftrightarrow: "\u21D4",
  Leftarrow: "\u21D0",
  Rightarrow: "\u21D2",
  leftrightarrow: "\u2194",
  leftarrow: "\u2190",
  gets: "\u2190",
  rightarrow: "\u2192",
  to: ["\u2192", { accent: false }],
  mapsto: "\u21A6",
  leftharpoonup: "\u21BC",
  leftharpoondown: "\u21BD",
  rightharpoonup: "\u21C0",
  rightharpoondown: "\u21C1",
  nearrow: "\u2197",
  searrow: "\u2198",
  nwarrow: "\u2196",
  swarrow: "\u2199",
  rightleftharpoons: "\u21CC",
  hookrightarrow: "\u21AA",
  hookleftarrow: "\u21A9",
  longleftarrow: "\u27F5",
  Longleftarrow: "\u27F8",
  longrightarrow: "\u27F6",
  Longrightarrow: "\u27F9",
  Longleftrightarrow: "\u27FA",
  longleftrightarrow: "\u27F7",
  longmapsto: "\u27FC",
  ldots: "\u2026",
  cdots: "\u22EF",
  vdots: "\u22EE",
  ddots: "\u22F1",
  iddots: "\u22F0",
  dotsc: "\u2026",
  dotsb: "\u22EF",
  dotsm: "\u22EF",
  dotsi: "\u22EF",
  dotso: "\u2026",
  ldotp: [".", { texClass: TEXCLASS.PUNCT }],
  cdotp: ["\u22C5", { texClass: TEXCLASS.PUNCT }],
  colon: [":", { texClass: TEXCLASS.PUNCT }]
});
new CharacterMap("mathchar7", ParseMethods_default.mathchar7, {
  _: "_",
  "#": "#",
  $: "$",
  "%": "%",
  "&": "&",
  And: "&"
});
new DelimiterMap("delimiter", ParseMethods_default.delimiter, {
  "(": "(",
  ")": ")",
  "[": "[",
  "]": "]",
  "<": "\u27E8",
  ">": "\u27E9",
  "\\lt": "\u27E8",
  "\\gt": "\u27E9",
  "/": "/",
  "|": ["|", { texClass: TEXCLASS.ORD }],
  ".": "",
  "\\lmoustache": "\u23B0",
  "\\rmoustache": "\u23B1",
  "\\lgroup": "\u27EE",
  "\\rgroup": "\u27EF",
  "\\arrowvert": "\u23D0",
  "\\Arrowvert": "\u2016",
  "\\bracevert": "\u23AA",
  "\\Vert": ["\u2016", { texClass: TEXCLASS.ORD }],
  "\\|": ["\u2016", { texClass: TEXCLASS.ORD }],
  "\\vert": ["|", { texClass: TEXCLASS.ORD }],
  "\\uparrow": "\u2191",
  "\\downarrow": "\u2193",
  "\\updownarrow": "\u2195",
  "\\Uparrow": "\u21D1",
  "\\Downarrow": "\u21D3",
  "\\Updownarrow": "\u21D5",
  "\\backslash": "\\",
  "\\rangle": "\u27E9",
  "\\langle": "\u27E8",
  "\\rbrace": "}",
  "\\lbrace": "{",
  "\\}": "}",
  "\\{": "{",
  "\\rceil": "\u2309",
  "\\lceil": "\u2308",
  "\\rfloor": "\u230B",
  "\\lfloor": "\u230A",
  "\\lbrack": "[",
  "\\rbrack": "]"
});
new CommandMap("macros", {
  displaystyle: [BaseMethods_default.SetStyle, "D", true, 0],
  textstyle: [BaseMethods_default.SetStyle, "T", false, 0],
  scriptstyle: [BaseMethods_default.SetStyle, "S", false, 1],
  scriptscriptstyle: [BaseMethods_default.SetStyle, "SS", false, 2],
  rm: [BaseMethods_default.SetFont, VARIANT.NORMAL],
  mit: [BaseMethods_default.SetFont, VARIANT.ITALIC],
  oldstyle: [BaseMethods_default.SetFont, VARIANT.OLDSTYLE],
  cal: [BaseMethods_default.SetFont, VARIANT.CALLIGRAPHIC],
  it: [BaseMethods_default.SetFont, VARIANT.MATHITALIC],
  bf: [BaseMethods_default.SetFont, VARIANT.BOLD],
  sf: [BaseMethods_default.SetFont, VARIANT.SANSSERIF],
  tt: [BaseMethods_default.SetFont, VARIANT.MONOSPACE],
  frak: [BaseMethods_default.MathFont, VARIANT.FRAKTUR],
  Bbb: [BaseMethods_default.MathFont, VARIANT.DOUBLESTRUCK],
  mathrm: [BaseMethods_default.MathFont, VARIANT.NORMAL],
  mathup: [BaseMethods_default.MathFont, VARIANT.NORMAL],
  mathnormal: [BaseMethods_default.MathFont, ""],
  mathbf: [BaseMethods_default.MathFont, VARIANT.BOLD],
  mathbfup: [BaseMethods_default.MathFont, VARIANT.BOLD],
  mathit: [BaseMethods_default.MathFont, VARIANT.MATHITALIC],
  mathbfit: [BaseMethods_default.MathFont, VARIANT.BOLDITALIC],
  mathbb: [BaseMethods_default.MathFont, VARIANT.DOUBLESTRUCK],
  mathfrak: [BaseMethods_default.MathFont, VARIANT.FRAKTUR],
  mathbffrak: [BaseMethods_default.MathFont, VARIANT.BOLDFRAKTUR],
  mathscr: [BaseMethods_default.MathFont, VARIANT.SCRIPT],
  mathbfscr: [BaseMethods_default.MathFont, VARIANT.BOLDSCRIPT],
  mathsf: [BaseMethods_default.MathFont, VARIANT.SANSSERIF],
  mathsfup: [BaseMethods_default.MathFont, VARIANT.SANSSERIF],
  mathbfsf: [BaseMethods_default.MathFont, VARIANT.BOLDSANSSERIF],
  mathbfsfup: [BaseMethods_default.MathFont, VARIANT.BOLDSANSSERIF],
  mathsfit: [BaseMethods_default.MathFont, VARIANT.SANSSERIFITALIC],
  mathbfsfit: [BaseMethods_default.MathFont, VARIANT.SANSSERIFBOLDITALIC],
  mathtt: [BaseMethods_default.MathFont, VARIANT.MONOSPACE],
  mathcal: [BaseMethods_default.MathFont, VARIANT.CALLIGRAPHIC],
  mathbfcal: [BaseMethods_default.MathFont, VARIANT.BOLDCALLIGRAPHIC],
  symrm: [BaseMethods_default.MathFont, VARIANT.NORMAL],
  symup: [BaseMethods_default.MathFont, VARIANT.NORMAL],
  symnormal: [BaseMethods_default.MathFont, ""],
  symbf: [BaseMethods_default.MathFont, VARIANT.BOLD, VARIANT.BOLDITALIC],
  symbfup: [BaseMethods_default.MathFont, VARIANT.BOLD],
  symit: [BaseMethods_default.MathFont, VARIANT.ITALIC],
  symbfit: [BaseMethods_default.MathFont, VARIANT.BOLDITALIC],
  symbb: [BaseMethods_default.MathFont, VARIANT.DOUBLESTRUCK],
  symfrak: [BaseMethods_default.MathFont, VARIANT.FRAKTUR],
  symbffrak: [BaseMethods_default.MathFont, VARIANT.BOLDFRAKTUR],
  symscr: [BaseMethods_default.MathFont, VARIANT.SCRIPT],
  symbfscr: [BaseMethods_default.MathFont, VARIANT.BOLDSCRIPT],
  symsf: [BaseMethods_default.MathFont, VARIANT.SANSSERIF, VARIANT.SANSSERIFITALIC],
  symsfup: [BaseMethods_default.MathFont, VARIANT.SANSSERIF],
  symbfsf: [BaseMethods_default.MathFont, VARIANT.BOLDSANSSERIF],
  symbfsfup: [BaseMethods_default.MathFont, VARIANT.BOLDSANSSERIF],
  symsfit: [BaseMethods_default.MathFont, VARIANT.SANSSERIFITALIC],
  symbfsfit: [BaseMethods_default.MathFont, VARIANT.SANSSERIFBOLDITALIC],
  symtt: [BaseMethods_default.MathFont, VARIANT.MONOSPACE],
  symcal: [BaseMethods_default.MathFont, VARIANT.CALLIGRAPHIC],
  symbfcal: [BaseMethods_default.MathFont, VARIANT.BOLDCALLIGRAPHIC],
  textrm: [BaseMethods_default.HBox, null, VARIANT.NORMAL],
  textup: [BaseMethods_default.HBox, null, VARIANT.NORMAL],
  textnormal: [BaseMethods_default.HBox],
  textit: [BaseMethods_default.HBox, null, VARIANT.ITALIC],
  textbf: [BaseMethods_default.HBox, null, VARIANT.BOLD],
  textsf: [BaseMethods_default.HBox, null, VARIANT.SANSSERIF],
  texttt: [BaseMethods_default.HBox, null, VARIANT.MONOSPACE],
  Tiny: [BaseMethods_default.SetSize, 0.5],
  tiny: [BaseMethods_default.SetSize, 0.6],
  scriptsize: [BaseMethods_default.SetSize, 0.7],
  SMALL: [BaseMethods_default.SetSize, 0.7],
  Small: [BaseMethods_default.SetSize, 0.8],
  footnotesize: [BaseMethods_default.SetSize, 0.8],
  small: [BaseMethods_default.SetSize, 0.9],
  normalsize: [BaseMethods_default.SetSize, 1],
  large: [BaseMethods_default.SetSize, 1.095],
  Large: [BaseMethods_default.SetSize, 1.2],
  LARGE: [BaseMethods_default.SetSize, 1.44],
  huge: [BaseMethods_default.SetSize, 1.728],
  Huge: [BaseMethods_default.SetSize, 2.074],
  HUGE: [BaseMethods_default.SetSize, 2.49],
  arcsin: BaseMethods_default.NamedFn,
  arccos: BaseMethods_default.NamedFn,
  arctan: BaseMethods_default.NamedFn,
  arg: BaseMethods_default.NamedFn,
  cos: BaseMethods_default.NamedFn,
  cosh: BaseMethods_default.NamedFn,
  cot: BaseMethods_default.NamedFn,
  coth: BaseMethods_default.NamedFn,
  csc: BaseMethods_default.NamedFn,
  deg: BaseMethods_default.NamedFn,
  det: BaseMethods_default.NamedOp,
  dim: BaseMethods_default.NamedFn,
  exp: BaseMethods_default.NamedFn,
  gcd: BaseMethods_default.NamedOp,
  hom: BaseMethods_default.NamedFn,
  inf: BaseMethods_default.NamedOp,
  ker: BaseMethods_default.NamedFn,
  lg: BaseMethods_default.NamedFn,
  lim: BaseMethods_default.NamedOp,
  liminf: [BaseMethods_default.NamedOp, "lim&thinsp;inf"],
  limsup: [BaseMethods_default.NamedOp, "lim&thinsp;sup"],
  ln: BaseMethods_default.NamedFn,
  log: BaseMethods_default.NamedFn,
  max: BaseMethods_default.NamedOp,
  min: BaseMethods_default.NamedOp,
  Pr: BaseMethods_default.NamedOp,
  sec: BaseMethods_default.NamedFn,
  sin: BaseMethods_default.NamedFn,
  sinh: BaseMethods_default.NamedFn,
  sup: BaseMethods_default.NamedOp,
  tan: BaseMethods_default.NamedFn,
  tanh: BaseMethods_default.NamedFn,
  limits: [BaseMethods_default.Limits, true],
  nolimits: [BaseMethods_default.Limits, false],
  overline: [BaseMethods_default.UnderOver, "2015"],
  underline: [BaseMethods_default.UnderOver, "2015"],
  overbrace: [BaseMethods_default.UnderOver, "23DE", true],
  underbrace: [BaseMethods_default.UnderOver, "23DF", true],
  overparen: [BaseMethods_default.UnderOver, "23DC"],
  underparen: [BaseMethods_default.UnderOver, "23DD"],
  overrightarrow: [BaseMethods_default.UnderOver, "2192"],
  underrightarrow: [BaseMethods_default.UnderOver, "2192"],
  overleftarrow: [BaseMethods_default.UnderOver, "2190"],
  underleftarrow: [BaseMethods_default.UnderOver, "2190"],
  overleftrightarrow: [BaseMethods_default.UnderOver, "2194"],
  underleftrightarrow: [BaseMethods_default.UnderOver, "2194"],
  overset: BaseMethods_default.Overset,
  underset: BaseMethods_default.Underset,
  overunderset: BaseMethods_default.Overunderset,
  stackrel: [BaseMethods_default.Macro, "\\mathrel{\\mathop{#2}\\limits^{#1}}", 2],
  stackbin: [BaseMethods_default.Macro, "\\mathbin{\\mathop{#2}\\limits^{#1}}", 2],
  over: BaseMethods_default.Over,
  overwithdelims: BaseMethods_default.Over,
  atop: BaseMethods_default.Over,
  atopwithdelims: BaseMethods_default.Over,
  above: BaseMethods_default.Over,
  abovewithdelims: BaseMethods_default.Over,
  brace: [BaseMethods_default.Over, "{", "}"],
  brack: [BaseMethods_default.Over, "[", "]"],
  choose: [BaseMethods_default.Over, "(", ")"],
  frac: BaseMethods_default.Frac,
  sqrt: BaseMethods_default.Sqrt,
  root: BaseMethods_default.Root,
  uproot: [BaseMethods_default.MoveRoot, "upRoot"],
  leftroot: [BaseMethods_default.MoveRoot, "leftRoot"],
  left: BaseMethods_default.LeftRight,
  right: BaseMethods_default.LeftRight,
  middle: BaseMethods_default.LeftRight,
  llap: BaseMethods_default.Lap,
  rlap: BaseMethods_default.Lap,
  raise: BaseMethods_default.RaiseLower,
  lower: BaseMethods_default.RaiseLower,
  moveleft: BaseMethods_default.MoveLeftRight,
  moveright: BaseMethods_default.MoveLeftRight,
  ",": [BaseMethods_default.Spacer, MATHSPACE.thinmathspace],
  ":": [BaseMethods_default.Spacer, MATHSPACE.mediummathspace],
  ">": [BaseMethods_default.Spacer, MATHSPACE.mediummathspace],
  ";": [BaseMethods_default.Spacer, MATHSPACE.thickmathspace],
  "!": [BaseMethods_default.Spacer, MATHSPACE.negativethinmathspace],
  enspace: [BaseMethods_default.Spacer, 0.5],
  quad: [BaseMethods_default.Spacer, 1],
  qquad: [BaseMethods_default.Spacer, 2],
  thinspace: [BaseMethods_default.Spacer, MATHSPACE.thinmathspace],
  negthinspace: [BaseMethods_default.Spacer, MATHSPACE.negativethinmathspace],
  "*": BaseMethods_default.DiscretionaryTimes,
  allowbreak: BaseMethods_default.AllowBreak,
  goodbreak: [BaseMethods_default.Linebreak, TexConstant.LineBreak.GOODBREAK],
  badbreak: [BaseMethods_default.Linebreak, TexConstant.LineBreak.BADBREAK],
  nobreak: [BaseMethods_default.Linebreak, TexConstant.LineBreak.NOBREAK],
  break: BaseMethods_default.Break,
  hskip: BaseMethods_default.Hskip,
  hspace: BaseMethods_default.Hskip,
  kern: [BaseMethods_default.Hskip, true],
  mskip: BaseMethods_default.Hskip,
  mspace: BaseMethods_default.Hskip,
  mkern: [BaseMethods_default.Hskip, true],
  rule: BaseMethods_default.rule,
  Rule: [BaseMethods_default.Rule],
  Space: [BaseMethods_default.Rule, "blank"],
  nonscript: BaseMethods_default.Nonscript,
  big: [BaseMethods_default.MakeBig, TEXCLASS.ORD, 0.85],
  Big: [BaseMethods_default.MakeBig, TEXCLASS.ORD, 1.15],
  bigg: [BaseMethods_default.MakeBig, TEXCLASS.ORD, 1.45],
  Bigg: [BaseMethods_default.MakeBig, TEXCLASS.ORD, 1.75],
  bigl: [BaseMethods_default.MakeBig, TEXCLASS.OPEN, 0.85],
  Bigl: [BaseMethods_default.MakeBig, TEXCLASS.OPEN, 1.15],
  biggl: [BaseMethods_default.MakeBig, TEXCLASS.OPEN, 1.45],
  Biggl: [BaseMethods_default.MakeBig, TEXCLASS.OPEN, 1.75],
  bigr: [BaseMethods_default.MakeBig, TEXCLASS.CLOSE, 0.85],
  Bigr: [BaseMethods_default.MakeBig, TEXCLASS.CLOSE, 1.15],
  biggr: [BaseMethods_default.MakeBig, TEXCLASS.CLOSE, 1.45],
  Biggr: [BaseMethods_default.MakeBig, TEXCLASS.CLOSE, 1.75],
  bigm: [BaseMethods_default.MakeBig, TEXCLASS.REL, 0.85],
  Bigm: [BaseMethods_default.MakeBig, TEXCLASS.REL, 1.15],
  biggm: [BaseMethods_default.MakeBig, TEXCLASS.REL, 1.45],
  Biggm: [BaseMethods_default.MakeBig, TEXCLASS.REL, 1.75],
  mathord: [BaseMethods_default.TeXAtom, TEXCLASS.ORD],
  mathop: [BaseMethods_default.TeXAtom, TEXCLASS.OP],
  mathopen: [BaseMethods_default.TeXAtom, TEXCLASS.OPEN],
  mathclose: [BaseMethods_default.TeXAtom, TEXCLASS.CLOSE],
  mathbin: [BaseMethods_default.TeXAtom, TEXCLASS.BIN],
  mathrel: [BaseMethods_default.TeXAtom, TEXCLASS.REL],
  mathpunct: [BaseMethods_default.TeXAtom, TEXCLASS.PUNCT],
  mathinner: [BaseMethods_default.TeXAtom, TEXCLASS.INNER],
  vtop: [BaseMethods_default.VBox, "top"],
  vcenter: [BaseMethods_default.VBox, "center"],
  vbox: [BaseMethods_default.VBox, "bottom"],
  hsize: BaseMethods_default.Hsize,
  parbox: BaseMethods_default.ParBox,
  breakAlign: BaseMethods_default.BreakAlign,
  buildrel: BaseMethods_default.BuildRel,
  hbox: [BaseMethods_default.HBox, 0],
  text: BaseMethods_default.HBox,
  mbox: [BaseMethods_default.HBox, 0],
  fbox: BaseMethods_default.FBox,
  boxed: [BaseMethods_default.Macro, "\\fbox{$\\displaystyle{#1}$}", 1],
  framebox: BaseMethods_default.FrameBox,
  makebox: BaseMethods_default.MakeBox,
  strut: BaseMethods_default.Strut,
  mathstrut: [BaseMethods_default.Macro, "\\vphantom{(}"],
  phantom: BaseMethods_default.Phantom,
  vphantom: [BaseMethods_default.Phantom, 1, 0],
  hphantom: [BaseMethods_default.Phantom, 0, 1],
  smash: BaseMethods_default.Smash,
  acute: [BaseMethods_default.Accent, "00B4"],
  grave: [BaseMethods_default.Accent, "0060"],
  ddot: [BaseMethods_default.Accent, "00A8"],
  dddot: [BaseMethods_default.Accent, "20DB"],
  ddddot: [BaseMethods_default.Accent, "20DC"],
  tilde: [BaseMethods_default.Accent, "007E"],
  bar: [BaseMethods_default.Accent, "00AF"],
  breve: [BaseMethods_default.Accent, "02D8"],
  check: [BaseMethods_default.Accent, "02C7"],
  hat: [BaseMethods_default.Accent, "005E"],
  vec: [BaseMethods_default.Accent, "2192", false],
  dot: [BaseMethods_default.Accent, "02D9"],
  widetilde: [BaseMethods_default.Accent, "007E", true],
  widehat: [BaseMethods_default.Accent, "005E", true],
  matrix: BaseMethods_default.Matrix,
  array: BaseMethods_default.Matrix,
  pmatrix: [BaseMethods_default.Matrix, "(", ")"],
  cases: [BaseMethods_default.Matrix, "{", "", "left left", null, ".2em", null, true],
  eqalign: [
    BaseMethods_default.Matrix,
    null,
    null,
    "right left",
    THICKMATHSPACE,
    ".5em",
    "D"
  ],
  displaylines: [BaseMethods_default.Matrix, null, null, "center", null, ".5em", "D"],
  cr: BaseMethods_default.Cr,
  "\\": BaseMethods_default.CrLaTeX,
  newline: [BaseMethods_default.CrLaTeX, true],
  hline: BaseMethods_default.HLine,
  hdashline: [BaseMethods_default.HLine, "dashed"],
  eqalignno: [
    BaseMethods_default.Matrix,
    null,
    null,
    "right left",
    THICKMATHSPACE,
    ".5em",
    "D",
    null,
    "right"
  ],
  leqalignno: [
    BaseMethods_default.Matrix,
    null,
    null,
    "right left",
    THICKMATHSPACE,
    ".5em",
    "D",
    null,
    "left"
  ],
  hfill: BaseMethods_default.HFill,
  hfil: BaseMethods_default.HFill,
  hfilll: BaseMethods_default.HFill,
  bmod: [
    BaseMethods_default.Macro,
    `\\mmlToken{mo}[lspace="${THICKMATHSPACE}" rspace="${THICKMATHSPACE}"]{mod}`
  ],
  pmod: [BaseMethods_default.Macro, "\\pod{\\mmlToken{mi}{mod}\\kern 6mu #1}", 1],
  mod: [
    BaseMethods_default.Macro,
    "\\mathchoice{\\kern18mu}{\\kern12mu}{\\kern12mu}{\\kern12mu}\\mmlToken{mi}{mod}\\,\\,#1",
    1
  ],
  pod: [
    BaseMethods_default.Macro,
    "\\mathchoice{\\kern18mu}{\\kern8mu}{\\kern8mu}{\\kern8mu}(#1)",
    1
  ],
  iff: [BaseMethods_default.Macro, "\\;\\Longleftrightarrow\\;"],
  skew: [BaseMethods_default.Macro, "{{#2{#3\\mkern#1mu}\\mkern-#1mu}{}}", 3],
  pmb: [BaseMethods_default.Macro, "\\rlap{#1}\\kern1px{#1}", 1],
  TeX: [BaseMethods_default.Macro, "T\\kern-.14em\\lower.5ex{E}\\kern-.115em X"],
  LaTeX: [
    BaseMethods_default.Macro,
    "L\\kern-.325em\\raise.21em{\\scriptstyle{A}}\\kern-.17em\\TeX"
  ],
  not: BaseMethods_default.Not,
  dots: BaseMethods_default.Dots,
  space: BaseMethods_default.Tilde,
  "\xA0": BaseMethods_default.Tilde,
  " ": BaseMethods_default.Tilde,
  begin: BaseMethods_default.BeginEnd,
  end: BaseMethods_default.BeginEnd,
  label: BaseMethods_default.HandleLabel,
  ref: BaseMethods_default.HandleRef,
  nonumber: BaseMethods_default.HandleNoTag,
  newcolumntype: BaseMethods_default.NewColumnType,
  mathchoice: BaseMethods_default.MathChoice,
  mmlToken: BaseMethods_default.MmlToken
});
new EnvironmentMap("environment", ParseMethods_default.environment, {
  displaymath: [BaseMethods_default.Equation, null, false],
  math: [BaseMethods_default.Equation, null, false, false],
  array: [BaseMethods_default.AlignedArray],
  darray: [BaseMethods_default.AlignedArray, null, "D"],
  equation: [BaseMethods_default.Equation, null, true],
  eqnarray: [
    BaseMethods_default.EqnArray,
    null,
    true,
    true,
    "rcl",
    "bmt",
    ParseUtil.cols(0, MATHSPACE.thickmathspace),
    ".5em"
  ],
  indentalign: [BaseMethods_default.IndentAlign]
});
new CharacterMap("not_remap", null, {
  "\u2190": "\u219A",
  "\u2192": "\u219B",
  "\u2194": "\u21AE",
  "\u21D0": "\u21CD",
  "\u21D2": "\u21CF",
  "\u21D4": "\u21CE",
  "\u2208": "\u2209",
  "\u220B": "\u220C",
  "\u2223": "\u2224",
  "\u2225": "\u2226",
  "\u223C": "\u2241",
  "~": "\u2241",
  "\u2243": "\u2244",
  "\u2245": "\u2247",
  "\u2248": "\u2249",
  "\u224D": "\u226D",
  "=": "\u2260",
  "\u2261": "\u2262",
  "<": "\u226E",
  ">": "\u226F",
  "\u2264": "\u2270",
  "\u2265": "\u2271",
  "\u2272": "\u2274",
  "\u2273": "\u2275",
  "\u2276": "\u2278",
  "\u2277": "\u2279",
  "\u227A": "\u2280",
  "\u227B": "\u2281",
  "\u2282": "\u2284",
  "\u2283": "\u2285",
  "\u2286": "\u2288",
  "\u2287": "\u2289",
  "\u22A2": "\u22AC",
  "\u22A8": "\u22AD",
  "\u22A9": "\u22AE",
  "\u22AB": "\u22AF",
  "\u227C": "\u22E0",
  "\u227D": "\u22E1",
  "\u2291": "\u22E2",
  "\u2292": "\u22E3",
  "\u22B2": "\u22EA",
  "\u22B3": "\u22EB",
  "\u22B4": "\u22EC",
  "\u22B5": "\u22ED",
  "\u2203": "\u2204"
});

// node_modules/@mathjax/src/mjs/input/tex/base/BaseConfiguration.js
var MATHVARIANT3 = TexConstant.Variant;
new CharacterMap("remap", null, {
  "-": "\u2212",
  "*": "\u2217",
  "`": "\u2018"
});
function Other(parser, char) {
  const font = parser.stack.env["font"];
  const ifont = parser.stack.env["italicFont"];
  const def = font ? { mathvariant: font } : {};
  const remap = MapHandler.getMap("remap").lookup(char);
  const range = getRange(char);
  const type = range[3];
  const mo = parser.create("token", type, def, remap ? remap.char : char);
  const style = ParseUtil.isLatinOrGreekChar(char) ? parser.configuration.mathStyle(char, true) || ifont : "";
  const variant = range[4] || (font && style === MATHVARIANT3.NORMAL ? "" : style);
  if (variant) {
    mo.attributes.set("mathvariant", variant);
  }
  if (type === "mo") {
    NodeUtil_default.setProperty(mo, "fixStretchy", true);
    parser.configuration.addNode("fixStretchy", mo);
  }
  parser.Push(mo);
}
function csUndefined(_parser, name) {
  throw new TexError_default("UndefinedControlSequence", "Undefined control sequence %1", "\\" + name);
}
function envUndefined(_parser, env) {
  throw new TexError_default("UnknownEnv", "Unknown environment '%1'", env);
}
function filterNonscript({ data }) {
  for (const mml of data.getList("nonscript")) {
    if (mml.attributes.get("scriptlevel") > 0) {
      const parent = mml.parent;
      parent.childNodes.splice(parent.childIndex(mml), 1);
      data.removeFromList(mml.kind, [mml]);
      if (mml.isKind("mrow")) {
        const mstyle = mml.childNodes[0];
        data.removeFromList("mstyle", [mstyle]);
        data.removeFromList("mspace", mstyle.childNodes[0].childNodes);
      }
    } else if (mml.isKind("mrow")) {
      mml.parent.replaceChild(mml.childNodes[0], mml);
      data.removeFromList("mrow", [mml]);
    }
  }
}
var BaseTags = class extends AbstractTags {
};
var BaseConfiguration = Configuration.create("base", {
  [ConfigurationType.CONFIG]: function(config, jax) {
    const options2 = jax.parseOptions.options;
    if (options2.digits) {
      options2.numberPattern = options2.digits;
    }
    new RegExpMap("digit", ParseMethods_default.digit, options2.initialDigit);
    new RegExpMap("letter", ParseMethods_default.variable, options2.initialLetter);
    const handler = config.handlers.get(HandlerType.CHARACTER);
    handler.add(["letter", "digit"], null, 4);
  },
  [ConfigurationType.HANDLER]: {
    [HandlerType.CHARACTER]: ["command", "special"],
    [HandlerType.DELIMITER]: ["delimiter"],
    [HandlerType.MACRO]: [
      "delimiter",
      "macros",
      "lcGreek",
      "ucGreek",
      "mathchar0mi",
      "mathchar0mo",
      "mathchar7"
    ],
    [HandlerType.ENVIRONMENT]: ["environment"]
  },
  [ConfigurationType.FALLBACK]: {
    [HandlerType.CHARACTER]: Other,
    [HandlerType.MACRO]: csUndefined,
    [HandlerType.ENVIRONMENT]: envUndefined
  },
  [ConfigurationType.ITEMS]: {
    [StartItem.prototype.kind]: StartItem,
    [StopItem.prototype.kind]: StopItem,
    [OpenItem.prototype.kind]: OpenItem,
    [CloseItem.prototype.kind]: CloseItem,
    [NullItem.prototype.kind]: NullItem,
    [PrimeItem.prototype.kind]: PrimeItem,
    [SubsupItem.prototype.kind]: SubsupItem,
    [OverItem.prototype.kind]: OverItem,
    [LeftItem.prototype.kind]: LeftItem,
    [Middle.prototype.kind]: Middle,
    [RightItem.prototype.kind]: RightItem,
    [BreakItem.prototype.kind]: BreakItem,
    [BeginItem.prototype.kind]: BeginItem,
    [EndItem.prototype.kind]: EndItem,
    [StyleItem.prototype.kind]: StyleItem,
    [PositionItem.prototype.kind]: PositionItem,
    [CellItem.prototype.kind]: CellItem,
    [MmlItem.prototype.kind]: MmlItem,
    [FnItem.prototype.kind]: FnItem,
    [NotItem.prototype.kind]: NotItem,
    [NonscriptItem.prototype.kind]: NonscriptItem,
    [DotsItem.prototype.kind]: DotsItem,
    [ArrayItem.prototype.kind]: ArrayItem,
    [EqnArrayItem.prototype.kind]: EqnArrayItem,
    [EquationItem.prototype.kind]: EquationItem,
    [MstyleItem.prototype.kind]: MstyleItem
  },
  [ConfigurationType.OPTIONS]: {
    maxMacros: 1e3,
    digits: "",
    numberPattern: /^(?:[0-9]+(?:\{,\}[0-9]{3})*(?:\.[0-9]*)?|\.[0-9]+)/,
    initialDigit: /[0-9.,]/,
    identifierPattern: /^[a-zA-Z]+/,
    initialLetter: /[a-zA-Z]/,
    baseURL: !context.document || context.document.getElementsByTagName("base").length === 0 ? "" : String(context.document.location).replace(/#.*$/, "")
  },
  [ConfigurationType.TAGS]: {
    base: BaseTags
  },
  [ConfigurationType.POSTPROCESSORS]: [[filterNonscript, -4]]
});

// node_modules/@mathjax/src/mjs/input/tex.js
var TeX = class _TeX extends AbstractInputJax {
  static configure(packages) {
    const configuration = new ParserConfiguration(packages, ["tex"]);
    configuration.init();
    return configuration;
  }
  static tags(options2, configuration) {
    TagsFactory.addTags(configuration.tags);
    TagsFactory.setDefault(options2.options.tags);
    options2.tags = TagsFactory.getDefault();
    options2.tags.configuration = options2;
  }
  constructor(options2 = {}) {
    const [rest, tex2, find] = separateOptions(options2, _TeX.OPTIONS, FindTeX.OPTIONS);
    super(tex2);
    this.findTeX = this.options["FindTeX"] || new FindTeX(find);
    const packages = this.options.packages;
    const configuration = this.configuration = _TeX.configure(packages);
    const parseOptions = this._parseOptions = new ParseOptions_default(configuration, [
      this.options,
      TagsFactory.OPTIONS
    ]);
    userOptions(parseOptions.options, rest);
    configuration.config(this);
    _TeX.tags(parseOptions, configuration);
    this.postFilters.addList([
      [FilterUtil_default.cleanSubSup, -7],
      [FilterUtil_default.setInherited, -6],
      [FilterUtil_default.checkScriptlevel, -5],
      [FilterUtil_default.moveLimits, -4],
      [FilterUtil_default.cleanStretchy, -3],
      [FilterUtil_default.cleanAttributes, -2],
      [FilterUtil_default.combineRelations, -1]
    ]);
  }
  setMmlFactory(mmlFactory) {
    super.setMmlFactory(mmlFactory);
    this._parseOptions.nodeFactory.setMmlFactory(mmlFactory);
  }
  get parseOptions() {
    return this._parseOptions;
  }
  reset(tag = 0) {
    this.parseOptions.clear();
    this.parseOptions.tags.reset(tag);
  }
  compile(math, document2) {
    this.parseOptions.clear();
    this.parseOptions.mathItem = math;
    this.executeFilters(this.preFilters, math, document2, this.parseOptions);
    this.latex = math.math;
    let node;
    this.parseOptions.tags.startEquation(math);
    let parser;
    try {
      parser = new TexParser(this.latex, { display: math.display, isInner: false }, this.parseOptions);
      node = parser.mml();
    } catch (err) {
      if (!(err instanceof TexError_default)) {
        throw err;
      }
      this.parseOptions.error = true;
      node = this.options.formatError(this, err);
    }
    node = this.parseOptions.nodeFactory.create("node", "math", [node]);
    node.attributes.set(TexConstant.Attr.LATEX, this.latex);
    if (math.display) {
      NodeUtil_default.setAttribute(node, "display", "block");
    }
    this.parseOptions.tags.finishEquation(math);
    this.parseOptions.root = node;
    this.executeFilters(this.postFilters, math, document2, this.parseOptions);
    if (parser && parser.stack.env.hsize) {
      NodeUtil_default.setAttribute(node, "maxwidth", parser.stack.env.hsize);
      NodeUtil_default.setAttribute(node, "overflow", "linebreak");
    }
    this.mathNode = this.parseOptions.root;
    return this.mathNode;
  }
  findMath(strings) {
    return this.findTeX.findMath(strings);
  }
  formatError(err) {
    const message = err.message.replace(/\n.*/, "");
    return this.parseOptions.nodeFactory.create("error", message, err.id, this.latex);
  }
};
TeX.NAME = "TeX";
TeX.OPTIONS = Object.assign(Object.assign({}, AbstractInputJax.OPTIONS), { FindTeX: null, packages: ["base"], maxBuffer: 5 * 1024, maxTemplateSubtitutions: 1e4, mathStyle: "TeX", formatError: (jax, err) => jax.formatError(err) });

// node_modules/@mathjax/src/mjs/core/DOMAdaptor.js
var AbstractDOMAdaptor = class {
  constructor(document2 = null) {
    this.canMeasureNodes = true;
    this.document = document2;
  }
  node(kind, def = {}, children = [], ns) {
    const node = this.create(kind, ns);
    this.setAttributes(node, def);
    for (const child of children) {
      this.append(node, child);
    }
    return node;
  }
  setProperty(node, name, value) {
    node[name] = value;
  }
  getProperty(node, name) {
    return node[name];
  }
  setAttributes(node, def) {
    if (def.style && typeof def.style !== "string") {
      for (const key of Object.keys(def.style)) {
        this.setStyle(node, key.replace(/-([a-z])/g, (_m, c) => c.toUpperCase()), def.style[key]);
      }
    }
    if (def.properties) {
      for (const key of Object.keys(def.properties)) {
        node[key] = def.properties[key];
      }
    }
    for (const key of Object.keys(def)) {
      if ((key !== "style" || typeof def.style === "string") && key !== "properties") {
        this.setAttribute(node, key, def[key]);
      }
    }
  }
  replace(nnode, onode) {
    this.insert(nnode, onode);
    this.remove(onode);
    return onode;
  }
  childNode(node, i) {
    return this.childNodes(node)[i];
  }
  allClasses(node) {
    const classes = this.getAttribute(node, "class");
    return !classes ? [] : classes.replace(/  +/g, " ").replace(/^ /, "").replace(/ $/, "").split(/ /);
  }
  cssText(node) {
    return this.kind(node) === "style" ? this.textContent(node) : "";
  }
};

// node_modules/@mathjax/src/mjs/adaptors/NodeMixin.js
var __awaiter = function(thisArg, _arguments, P, generator) {
  function adopt(value) {
    return value instanceof P ? value : new P(function(resolve) {
      resolve(value);
    });
  }
  return new (P || (P = Promise))(function(resolve, reject) {
    function fulfilled(value) {
      try {
        step(generator.next(value));
      } catch (e) {
        reject(e);
      }
    }
    function rejected(value) {
      try {
        step(generator["throw"](value));
      } catch (e) {
        reject(e);
      }
    }
    function step(result) {
      result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
    }
    step((generator = generator.apply(thisArg, _arguments || [])).next());
  });
};
var NodeMixinOptions = {
  badCSS: true,
  badSizes: true
};
function NodeMixin(Base, options2 = {}) {
  var _a;
  options2 = userOptions(defaultOptions({}, NodeMixinOptions), options2);
  return _a = class NodeAdaptor extends Base {
    constructor(...args) {
      super(args[0]);
      this.canMeasureNodes = false;
      const CLASS = this.constructor;
      this.options = userOptions(defaultOptions({}, CLASS.OPTIONS), args[1]);
    }
    fontSize(node) {
      return options2.badCSS ? this.options.fontSize : super.fontSize(node);
    }
    fontFamily(node) {
      return options2.badCSS ? this.options.fontFamily : super.fontFamily(node);
    }
    nodeSize(node, em2 = 1, local = null) {
      if (!options2.badSizes) {
        return super.nodeSize(node, em2, local);
      }
      const text = this.textContent(node);
      const non = Array.from(text.replace(_a.cjkPattern, "")).length;
      const CJK = Array.from(text).length - non;
      return [
        CJK * this.options.cjkCharWidth + non * this.options.unknownCharWidth,
        this.options.unknownCharHeight
      ];
    }
    nodeBBox(node) {
      return options2.badSizes ? { left: 0, right: 0, top: 0, bottom: 0 } : super.nodeBBox(node);
    }
    createWorker(listener, options3) {
      return __awaiter(this, void 0, void 0, function* () {
        const { Worker } = yield asyncLoad("node:worker_threads");
        class LiteWorker {
          constructor(url2, options4 = {}) {
            this.worker = new Worker(url2, options4);
          }
          addEventListener(kind, listener2) {
            this.worker.on(kind, listener2);
          }
          postMessage(msg) {
            this.worker.postMessage({ data: msg });
          }
          terminate() {
            this.worker.terminate();
          }
        }
        const { path, maps: maps3 } = options3;
        const url = `${path}/${options3.worker}`;
        const worker = new LiteWorker(url, {
          type: "module",
          workerData: { maps: maps3 }
        });
        worker.addEventListener("message", listener);
        return worker;
      });
    }
  }, _a.OPTIONS = Object.assign(Object.assign({}, options2.badCSS ? {
    fontSize: 16,
    fontFamily: "Times"
  } : {}), options2.badSizes ? {
    cjkCharWidth: 1,
    unknownCharWidth: 0.6,
    unknownCharHeight: 0.8
  } : {}), _a.cjkPattern = new RegExp([
    "[",
    "\u1100-\u115F",
    "\u2329\u232A",
    "\u2E80-\u303E",
    "\u3040-\u3247",
    "\u3250-\u4DBF",
    "\u4E00-\uA4C6",
    "\uA960-\uA97C",
    "\uAC00-\uD7A3",
    "\uF900-\uFAFF",
    "\uFE10-\uFE19",
    "\uFE30-\uFE6B",
    "\uFF01-\uFF60\uFFE0-\uFFE6",
    "\u{1B000}-\u{1B001}",
    "\u{1F200}-\u{1F251}",
    "\u{20000}-\u{3FFFD}",
    "]"
  ].join(""), "gu"), _a;
}

// node_modules/@mathjax/src/mjs/adaptors/lite/Element.js
var LiteElement = class {
  constructor(kind, attributes = {}, children = []) {
    this.kind = kind;
    this.attributes = Object.assign({}, attributes);
    this.children = [...children];
    for (const child of this.children) {
      child.parent = this;
    }
    this.styles = null;
  }
};

// node_modules/@mathjax/src/mjs/adaptors/lite/Document.js
var LiteDocument = class {
  get kind() {
    return "#document";
  }
  constructor(window2 = null) {
    this.defaultView = null;
    this.root = new LiteElement("html", {}, [
      this.head = new LiteElement("head"),
      this.body = new LiteElement("body")
    ]);
    this.type = "";
    this.defaultView = window2;
  }
};

// node_modules/@mathjax/src/mjs/adaptors/lite/Text.js
var LiteText = class {
  get kind() {
    return "#text";
  }
  constructor(text = "") {
    this.value = text;
  }
};
var LiteComment = class extends LiteText {
  get kind() {
    return "#comment";
  }
};

// node_modules/@mathjax/src/mjs/adaptors/lite/List.js
var LiteList = class {
  constructor(children) {
    this.nodes = [];
    this.nodes = [...children];
  }
  append(node) {
    this.nodes.push(node);
  }
  [Symbol.iterator]() {
    let i = 0;
    return {
      next() {
        return i === this.nodes.length ? { value: null, done: true } : { value: this.nodes[i++], done: false };
      }
    };
  }
};

// node_modules/@mathjax/src/mjs/adaptors/lite/Parser.js
var SPACE = "[ \\n]+";
var OPTIONALSPACE = "[ \\n]*";
var TAGNAME = `[A-Za-z][^\0- "'>/=\x7F-\x9F]*`;
var ATTNAME = `[^\0- "'>/=\x7F-\x9F]+`;
var VALUE = `(?:'[^']*'|"[^"]*"|${SPACE})`;
var VALUESPLIT = `(?:'([^']*)'|"([^"]*)"|(${SPACE}))`;
var ATTRIBUTE = `${ATTNAME}(?:${OPTIONALSPACE}=${OPTIONALSPACE}${VALUE})?`;
var ATTRIBUTESPLIT = `(${ATTNAME})(?:${OPTIONALSPACE}=${OPTIONALSPACE}${VALUESPLIT})?`;
var TAG = `(<(?:${TAGNAME}(?:${SPACE}${ATTRIBUTE})*${OPTIONALSPACE}/?|/${TAGNAME}|!--[^]*?--|![^]*?)(?:>|$))`;
var PATTERNS = {
  tag: new RegExp(TAG, "u"),
  attr: new RegExp(ATTRIBUTE, "u"),
  attrsplit: new RegExp(ATTRIBUTESPLIT, "u")
};
var LiteParser = class {
  parseFromString(text, _format = "text/html", adaptor2 = null) {
    const root = adaptor2.createDocument();
    let node = adaptor2.body(root);
    const parts = text.replace(/<\?.*?\?>/g, "").split(PATTERNS.tag);
    while (parts.length) {
      const text2 = parts.shift();
      const tag = parts.shift();
      if (text2) {
        this.addText(adaptor2, node, text2);
      }
      if (tag && tag.charAt(tag.length - 1) === ">") {
        if (tag.charAt(1) === "!") {
          this.addComment(adaptor2, node, tag);
        } else if (tag.charAt(1) === "/") {
          node = this.closeTag(adaptor2, node, tag);
        } else {
          node = this.openTag(adaptor2, node, tag, parts);
        }
      }
    }
    this.checkDocument(adaptor2, root);
    return root;
  }
  addText(adaptor2, node, text) {
    text = translate(text);
    return adaptor2.append(node, adaptor2.text(text));
  }
  addComment(adaptor2, node, comment) {
    return adaptor2.append(node, new LiteComment(comment));
  }
  closeTag(adaptor2, node, tag) {
    const kind = tag.slice(2, tag.length - 1).toLowerCase();
    while (adaptor2.parent(node) && adaptor2.kind(node) !== kind) {
      node = adaptor2.parent(node);
    }
    return adaptor2.parent(node);
  }
  openTag(adaptor2, node, tag, parts) {
    const PCDATA = this.constructor.PCDATA;
    const SELF_CLOSING = this.constructor.SELF_CLOSING;
    const kind = tag.match(/<(.*?)[\s\n>/]/)[1].toLowerCase();
    const child = adaptor2.node(kind);
    const attributes = tag.replace(/^<.*?[\s\n>]/, "").split(PATTERNS.attrsplit);
    if (attributes.pop().match(/>$/) || attributes.length < 5) {
      this.addAttributes(adaptor2, child, attributes);
      adaptor2.append(node, child);
      if (!SELF_CLOSING[kind] && !tag.match(/\/>$/)) {
        if (PCDATA[kind]) {
          this.handlePCDATA(adaptor2, child, kind, parts);
        } else {
          node = child;
        }
      }
    }
    return node;
  }
  addAttributes(adaptor2, node, attributes) {
    while (attributes.length) {
      const [, name, v1, v2, v3] = attributes.splice(0, 5);
      const value = translate(v1 || v2 || v3 || "");
      adaptor2.setAttribute(node, name, value);
    }
  }
  handlePCDATA(adaptor2, node, kind, parts) {
    const pcdata = [];
    const etag = "</" + kind + ">";
    let ptag = "";
    while (parts.length && ptag !== etag) {
      pcdata.push(ptag);
      pcdata.push(parts.shift());
      ptag = parts.shift();
    }
    adaptor2.append(node, adaptor2.text(pcdata.join("")));
  }
  checkDocument(adaptor2, root) {
    const node = this.getOnlyChild(adaptor2, adaptor2.body(root));
    if (!node)
      return;
    for (const child of adaptor2.childNodes(adaptor2.body(root))) {
      if (child === node) {
        break;
      }
      if (child instanceof LiteComment && child.value.match(/^<!DOCTYPE/)) {
        root.type = child.value;
      }
    }
    switch (adaptor2.kind(node)) {
      case "html":
        for (const child of node.children) {
          switch (adaptor2.kind(child)) {
            case "head":
              root.head = child;
              break;
            case "body":
              root.body = child;
              break;
          }
        }
        root.root = node;
        adaptor2.remove(node);
        if (adaptor2.parent(root.body) !== node) {
          adaptor2.append(node, root.body);
        }
        if (adaptor2.parent(root.head) !== node) {
          adaptor2.insert(root.head, root.body);
        }
        break;
      case "head":
        root.head = adaptor2.replace(node, root.head);
        break;
      case "body":
        root.body = adaptor2.replace(node, root.body);
        break;
    }
  }
  getOnlyChild(adaptor2, body) {
    let node = null;
    for (const child of adaptor2.childNodes(body)) {
      if (child instanceof LiteElement) {
        if (node)
          return null;
        node = child;
      }
    }
    return node;
  }
  serialize(adaptor2, node, xml = false) {
    const SELF_CLOSING = this.constructor.SELF_CLOSING;
    const tag = adaptor2.kind(node);
    const attributes = this.allAttributes(adaptor2, node, xml).map((x) => x.name + '="' + this.protectAttribute(x.value, xml) + '"').join(" ");
    const content = this.serializeInner(adaptor2, node, xml);
    const html = `<${tag}` + (attributes ? " " + attributes : "") + ((!xml || content) && !SELF_CLOSING[tag] ? `>${content}</${tag}>` : xml ? "/>" : ">");
    return html;
  }
  serializeInner(adaptor2, node, xml = false) {
    const PCDATA = this.constructor.PCDATA;
    if (Object.hasOwn(PCDATA, node.kind)) {
      return adaptor2.childNodes(node).map((x) => adaptor2.value(x)).join("");
    }
    return adaptor2.childNodes(node).map((x) => {
      const kind = adaptor2.kind(x);
      return kind === "#text" ? this.protectHTML(adaptor2.value(x)) : kind === "#comment" ? x.value : this.serialize(adaptor2, x, xml);
    }).join("");
  }
  allAttributes(adaptor2, node, xml) {
    const attributes = adaptor2.allAttributes(node);
    if (!xml) {
      return attributes;
    }
    const kind = adaptor2.kind(node);
    const xmlns = this.constructor.XMLNS;
    if (!Object.hasOwn(xmlns, kind)) {
      return attributes;
    }
    for (const { name } of attributes) {
      if (name === "xmlns") {
        return attributes;
      }
    }
    attributes.push({ name: "xmlns", value: xmlns[kind] });
    return attributes;
  }
  protectAttribute(text, xml) {
    if (typeof text !== "string") {
      text = String(text);
    }
    text = text.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
    if (xml) {
      text = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
    return text;
  }
  protectHTML(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
};
LiteParser.SELF_CLOSING = {
  area: true,
  base: true,
  br: true,
  col: true,
  command: true,
  embed: true,
  hr: true,
  img: true,
  input: true,
  keygen: true,
  link: true,
  menuitem: true,
  meta: true,
  param: true,
  source: true,
  track: true,
  wbr: true
};
LiteParser.PCDATA = {
  option: true,
  textarea: true,
  fieldset: true,
  title: true,
  style: true,
  script: true
};
LiteParser.XMLNS = {
  svg: "http://www.w3.org/2000/svg",
  math: "http://www.w3.org/1998/Math/MathML",
  html: "http://www.w3.org/1999/xhtml"
};

// node_modules/@mathjax/src/mjs/adaptors/lite/Window.js
var LiteWindow = class {
  constructor() {
    this.DOMParser = LiteParser;
    this.NodeList = LiteList;
    this.HTMLCollection = LiteList;
    this.HTMLElement = LiteElement;
    this.DocumentFragment = LiteList;
    this.Document = LiteDocument;
    this.document = new LiteDocument(this);
  }
};

// node_modules/@mathjax/src/mjs/adaptors/liteAdaptor.js
var __awaiter2 = function(thisArg, _arguments, P, generator) {
  function adopt(value) {
    return value instanceof P ? value : new P(function(resolve) {
      resolve(value);
    });
  }
  return new (P || (P = Promise))(function(resolve, reject) {
    function fulfilled(value) {
      try {
        step(generator.next(value));
      } catch (e) {
        reject(e);
      }
    }
    function rejected(value) {
      try {
        step(generator["throw"](value));
      } catch (e) {
        reject(e);
      }
    }
    function step(result) {
      result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
    }
    step((generator = generator.apply(thisArg, _arguments || [])).next());
  });
};
var LiteBase = class extends AbstractDOMAdaptor {
  constructor() {
    super();
    this.parser = new LiteParser();
    this.window = new LiteWindow();
  }
  parse(text, format) {
    return this.parser.parseFromString(text, format, this);
  }
  create(kind, _ns = null) {
    return new LiteElement(kind);
  }
  text(text) {
    return new LiteText(text);
  }
  comment(text) {
    return new LiteComment(text);
  }
  createDocument() {
    return new LiteDocument();
  }
  head(doc = this.document) {
    return doc.head;
  }
  body(doc = this.document) {
    return doc.body;
  }
  root(doc = this.document) {
    return doc.root;
  }
  doctype(doc = this.document) {
    return doc.type;
  }
  tags(node, name, ns = null, stop = null) {
    let stack = [];
    const tags = [];
    if (ns) {
      return tags;
    }
    let n = node;
    while (n) {
      const kind = n.kind;
      if (kind !== "#text" && kind !== "#comment") {
        n = n;
        if (kind === name) {
          tags.push(n);
          if (tags.length === stop) {
            return tags;
          }
        }
        if (n.children.length) {
          stack = n.children.concat(stack);
        }
      }
      n = stack.shift();
    }
    return tags;
  }
  elementById(node, id) {
    let stack = [];
    let n = node;
    while (n) {
      if (n.kind !== "#text" && n.kind !== "#comment") {
        n = n;
        if (n.attributes["id"] === id) {
          return n;
        }
        if (n.children.length) {
          stack = n.children.concat(stack);
        }
      }
      n = stack.shift();
    }
    return null;
  }
  elementsByClass(node, name, stop = null) {
    let stack = [];
    const tags = [];
    let n = node;
    while (n) {
      if (n.kind !== "#text" && n.kind !== "#comment") {
        n = n;
        const classes = (n.attributes["class"] || "").trim().split(/ +/);
        if (classes.includes(name)) {
          tags.push(n);
          if (tags.length === stop) {
            return tags;
          }
        }
        if (n.children.length) {
          stack = n.children.concat(stack);
        }
      }
      n = stack.shift();
    }
    return tags;
  }
  elementsByAttribute(node, name, value, stop = null) {
    let stack = [];
    const tags = [];
    let n = node;
    while (n) {
      if (n.kind !== "#text" && n.kind !== "#comment") {
        n = n;
        const attribute = n.attributes[name];
        if (attribute === value) {
          tags.push(n);
          if (tags.length === stop) {
            return tags;
          }
        }
        if (n.children.length) {
          stack = n.children.concat(stack);
        }
      }
      n = stack.shift();
    }
    return tags;
  }
  getElements(nodes, document2) {
    let containers = [];
    const body = this.body(document2);
    for (const node of nodes) {
      if (typeof node === "string") {
        if (node.charAt(0) === "#") {
          const n = this.elementById(body, node.slice(1));
          if (n) {
            containers.push(n);
          }
        } else if (node.charAt(0) === ".") {
          containers = containers.concat(this.elementsByClass(body, node.slice(1)));
        } else if (node.match(/^[-a-z][-a-z0-9]*$/i)) {
          containers = containers.concat(this.tags(body, node));
        } else {
          const match = node.match(/^\[(.*?)="(.*?)"\]$/);
          if (match) {
            containers = containers.concat(this.elementsByAttribute(body, match[1], match[2]));
          }
        }
      } else if (Array.isArray(node)) {
        containers = containers.concat(node);
      } else if (node instanceof this.window.NodeList || node instanceof this.window.HTMLCollection) {
        containers = containers.concat(node.nodes);
      } else {
        containers.push(node);
      }
    }
    return containers;
  }
  getElement(selector, node = this.document) {
    if (node instanceof LiteDocument) {
      node = this.body(node);
    }
    if (selector.charAt(0) === "#") {
      return this.elementById(node, selector.slice(1));
    }
    if (selector.charAt(0) === ".") {
      return this.elementsByClass(node, selector.slice(1), 1)[0];
    }
    if (selector.match(/^[-a-z][-a-z0-9]*$/i)) {
      return this.tags(node, selector, null, 1)[0];
    }
    const match = selector.match(/^\[(.*?)="(.*?)"\]$/);
    if (match) {
      return this.elementsByAttribute(node, match[1], match[2], 1)[0];
    }
    return null;
  }
  contains(container, node) {
    while (node && node !== container) {
      node = this.parent(node);
    }
    return !!node;
  }
  parent(node) {
    return node.parent;
  }
  childIndex(node) {
    return node.parent ? node.parent.children.findIndex((n) => n === node) : -1;
  }
  append(node, child) {
    if (child.parent) {
      this.remove(child);
    }
    node.children.push(child);
    child.parent = node;
    return child;
  }
  insert(nchild, ochild) {
    if (nchild.parent) {
      this.remove(nchild);
    }
    if (ochild && ochild.parent) {
      const i = this.childIndex(ochild);
      ochild.parent.children.splice(i, 0, nchild);
      nchild.parent = ochild.parent;
    }
  }
  remove(child) {
    const i = this.childIndex(child);
    if (i >= 0) {
      child.parent.children.splice(i, 1);
    }
    child.parent = null;
    return child;
  }
  replace(nnode, onode) {
    const i = this.childIndex(onode);
    if (i >= 0) {
      onode.parent.children[i] = nnode;
      nnode.parent = onode.parent;
      onode.parent = null;
    }
    return onode;
  }
  clone(node, deep = true) {
    const nnode = new LiteElement(node.kind);
    nnode.attributes = Object.assign({}, node.attributes);
    nnode.children = !deep ? [] : node.children.map((n) => {
      if (n.kind === "#text") {
        return new LiteText(n.value);
      } else if (n.kind === "#comment") {
        return new LiteComment(n.value);
      } else {
        const m = this.clone(n);
        m.parent = nnode;
        return m;
      }
    });
    return nnode;
  }
  split(node, n) {
    const text = new LiteText(node.value.slice(n));
    node.value = node.value.slice(0, n);
    node.parent.children.splice(this.childIndex(node) + 1, 0, text);
    text.parent = node.parent;
    return text;
  }
  next(node) {
    const parent = node.parent;
    if (!parent)
      return null;
    const i = this.childIndex(node) + 1;
    return i >= 0 && i < parent.children.length ? parent.children[i] : null;
  }
  previous(node) {
    const parent = node.parent;
    if (!parent)
      return null;
    const i = this.childIndex(node) - 1;
    return i >= 0 ? parent.children[i] : null;
  }
  firstChild(node) {
    return node.children[0];
  }
  lastChild(node) {
    return node.children[node.children.length - 1];
  }
  childNodes(node) {
    return [...node.children];
  }
  childNode(node, i) {
    return node.children[i];
  }
  kind(node) {
    return node.kind;
  }
  value(node) {
    return node.kind === "#text" ? node.value : node.kind === "#comment" ? node.value.replace(/^<!(--)?((?:.|\n)*)\1>$/, "$2") : "";
  }
  textContent(node) {
    return node.children.reduce((s, n) => {
      return s + (n.kind === "#text" ? n.value : n.kind === "#comment" ? "" : this.textContent(n));
    }, "");
  }
  innerHTML(node) {
    return this.parser.serializeInner(this, node);
  }
  outerHTML(node) {
    return this.parser.serialize(this, node);
  }
  serializeXML(node) {
    return this.parser.serialize(this, node, true);
  }
  setAttribute(node, name, value, ns = null) {
    if (typeof value !== "string") {
      value = String(value);
    }
    if (ns) {
      name = ns.replace(/.*\//, "") + ":" + name.replace(/^.*:/, "");
    }
    node.attributes[name] = value;
    if (name === "style") {
      node.styles = null;
    }
  }
  getAttribute(node, name) {
    return node.attributes[name];
  }
  removeAttribute(node, name) {
    delete node.attributes[name];
  }
  hasAttribute(node, name) {
    return Object.hasOwn(node.attributes, name);
  }
  allAttributes(node) {
    const attributes = node.attributes;
    const list = [];
    for (const name of Object.keys(attributes)) {
      list.push({ name, value: attributes[name] });
    }
    return list;
  }
  addClass(node, name) {
    const classString = node.attributes["class"];
    const classes = (classString === null || classString === void 0 ? void 0 : classString.split(/ /)) || [];
    if (!classes.includes(name)) {
      classes.push(name);
      node.attributes["class"] = classes.join(" ");
    }
  }
  removeClass(node, name) {
    const classString = node.attributes["class"];
    const classes = (classString === null || classString === void 0 ? void 0 : classString.split(/ /)) || [];
    const i = classes.indexOf(name);
    if (i >= 0) {
      classes.splice(i, 1);
      node.attributes["class"] = classes.join(" ");
    }
  }
  hasClass(node, name) {
    const classes = (node.attributes["class"] || "").split(/ /);
    return classes.includes(name);
  }
  setStyle(node, name, value) {
    if (!node.styles) {
      node.styles = new Styles(this.getAttribute(node, "style"));
    }
    node.styles.set(name, value);
    node.attributes["style"] = node.styles.cssText;
  }
  getStyle(node, name) {
    if (!node.styles) {
      const style = this.getAttribute(node, "style");
      if (!style) {
        return "";
      }
      node.styles = new Styles(style);
    }
    return node.styles.get(name);
  }
  allStyles(node) {
    return this.getAttribute(node, "style");
  }
  insertRules(node, rules) {
    node.children = [
      this.text(this.textContent(node) + "\n\n" + rules.join("\n\n"))
    ];
  }
  fontSize(_node) {
    return 0;
  }
  fontFamily(_node) {
    return "";
  }
  nodeSize(_node, _em = 1, _local = null) {
    return [0, 0];
  }
  nodeBBox(_node) {
    return { left: 0, right: 0, top: 0, bottom: 0 };
  }
  createWorker() {
    return __awaiter2(this, void 0, void 0, function* () {
      return null;
    });
  }
};
var LiteAdaptor = class extends NodeMixin(LiteBase) {
};
function liteAdaptor(options2 = null) {
  return new LiteAdaptor(null, options2);
}

// node_modules/@mathjax/src/mjs/core/OutputJax.js
var AbstractOutputJax = class {
  constructor(options2 = {}) {
    this.adaptor = null;
    const CLASS = this.constructor;
    this.options = userOptions(defaultOptions({}, CLASS.OPTIONS), options2);
    this.preFilters = new FunctionList(this.options.preFilters);
    this.postFilters = new FunctionList(this.options.postFilters);
  }
  get name() {
    return this.constructor.NAME;
  }
  setAdaptor(adaptor2) {
    this.adaptor = adaptor2;
  }
  initialize() {
  }
  reset(..._args) {
  }
  getMetrics(_document) {
  }
  styleSheet(_document) {
    return null;
  }
  pageElements(_document) {
    return null;
  }
  executeFilters(filters, math, document2, data) {
    const args = { math, document: document2, data };
    filters.execute(args);
    return args.data;
  }
};
AbstractOutputJax.NAME = "generic";
AbstractOutputJax.OPTIONS = {
  preFilters: [],
  postFilters: []
};

// node_modules/@mathjax/src/mjs/util/LinkedList.js
var END = Symbol();
var ListItem = class {
  constructor(data = null) {
    this.next = null;
    this.prev = null;
    this.data = data;
  }
};
var LinkedList = class _LinkedList {
  constructor(...args) {
    this.list = new ListItem(END);
    this.list.next = this.list.prev = this.list;
    this.push(...args);
  }
  isBefore(a, b) {
    return a < b;
  }
  push(...args) {
    for (const data of args) {
      const item = new ListItem(data);
      item.next = this.list;
      item.prev = this.list.prev;
      this.list.prev = item;
      item.prev.next = item;
    }
    return this;
  }
  pop() {
    const item = this.list.prev;
    if (item.data === END) {
      return null;
    }
    this.list.prev = item.prev;
    item.prev.next = this.list;
    item.next = item.prev = null;
    return item.data;
  }
  unshift(...args) {
    for (const data of args.slice(0).reverse()) {
      const item = new ListItem(data);
      item.next = this.list.next;
      item.prev = this.list;
      this.list.next = item;
      item.next.prev = item;
    }
    return this;
  }
  shift() {
    const item = this.list.next;
    if (item.data === END) {
      return null;
    }
    this.list.next = item.next;
    item.next.prev = this.list;
    item.next = item.prev = null;
    return item.data;
  }
  remove(...items) {
    const map = /* @__PURE__ */ new Map();
    for (const item2 of items) {
      map.set(item2, true);
    }
    let item = this.list.next;
    while (item.data !== END) {
      const next = item.next;
      if (map.has(item.data)) {
        item.prev.next = item.next;
        item.next.prev = item.prev;
        item.next = item.prev = null;
      }
      item = next;
    }
    return this;
  }
  clear() {
    this.list.next.prev = this.list.prev.next = null;
    this.list.next = this.list.prev = this.list;
    return this;
  }
  *[Symbol.iterator]() {
    let current = this.list.next;
    while (current.data !== END) {
      yield current.data;
      current = current.next;
    }
  }
  *reversed() {
    let current = this.list.prev;
    while (current.data !== END) {
      yield current.data;
      current = current.prev;
    }
  }
  insert(data, isBefore = null) {
    if (isBefore === null) {
      isBefore = this.isBefore.bind(this);
    }
    const item = new ListItem(data);
    let cur = this.list.next;
    while (cur.data !== END && isBefore(cur.data, item.data)) {
      cur = cur.next;
    }
    item.prev = cur.prev;
    item.next = cur;
    cur.prev.next = cur.prev = item;
    return this;
  }
  sort(isBefore = null) {
    if (isBefore === null) {
      isBefore = this.isBefore.bind(this);
    }
    const lists = [];
    for (const item of this) {
      lists.push(new _LinkedList(item));
    }
    this.list.next = this.list.prev = this.list;
    while (lists.length > 1) {
      const l1 = lists.shift();
      const l2 = lists.shift();
      l1.merge(l2, isBefore);
      lists.push(l1);
    }
    if (lists.length) {
      this.list = lists[0].list;
    }
    return this;
  }
  merge(list, isBefore = null) {
    if (isBefore === null) {
      isBefore = this.isBefore.bind(this);
    }
    let lcur = this.list.next;
    let mcur = list.list.next;
    while (lcur.data !== END && mcur.data !== END) {
      if (isBefore(mcur.data, lcur.data)) {
        [mcur.prev.next, lcur.prev.next] = [lcur, mcur];
        [mcur.prev, lcur.prev] = [lcur.prev, mcur.prev];
        [this.list.prev.next, list.list.prev.next] = [list.list, this.list];
        [this.list.prev, list.list.prev] = [list.list.prev, this.list.prev];
        [lcur, mcur] = [mcur.next, lcur];
      } else {
        lcur = lcur.next;
      }
    }
    if (mcur.data !== END) {
      this.list.prev.next = list.list.next;
      list.list.next.prev = this.list.prev;
      list.list.prev.next = this.list;
      this.list.prev = list.list.prev;
      list.list.next = list.list.prev = list.list;
    }
    return this;
  }
};

// node_modules/@mathjax/src/mjs/core/MathList.js
var AbstractMathList = class extends LinkedList {
  isBefore(a, b) {
    return a.start.i < b.start.i || a.start.i === b.start.i && a.start.n < b.start.n;
  }
};

// node_modules/@mathjax/src/mjs/core/Tree/NodeFactory.js
var AbstractNodeFactory = class extends AbstractFactory {
  create(kind, properties = {}, children = []) {
    return this.node[kind](properties, children);
  }
};

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/math.js
var MmlMath = class extends AbstractMmlLayoutNode {
  get kind() {
    return "math";
  }
  get linebreakContainer() {
    return true;
  }
  get linebreakAlign() {
    return "";
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    if (this.attributes.get("mode") === "display") {
      this.attributes.setInherited("display", "block");
    }
    attributes = this.addInheritedAttributes(attributes, this.attributes.getAllAttributes());
    display = !!this.attributes.get("displaystyle") || !this.attributes.get("displaystyle") && this.attributes.get("display") === "block";
    this.attributes.setInherited("displaystyle", display);
    level = this.attributes.get("scriptlevel") || this.constructor.defaults["scriptlevel"];
    super.setChildInheritedAttributes(attributes, display, level, prime);
  }
  verifyTree(options2 = null) {
    super.verifyTree(options2);
    if (this.parent) {
      this.mError("Improper nesting of math tags", options2, true);
    }
  }
};
MmlMath.defaults = Object.assign(Object.assign({}, AbstractMmlLayoutNode.defaults), { mathvariant: "normal", mathsize: "normal", mathcolor: "", mathbackground: "transparent", dir: "ltr", scriptlevel: 0, displaystyle: false, display: "inline", maxwidth: "", overflow: "linebreak", altimg: "", "altimg-width": "", "altimg-height": "", "altimg-valign": "", alttext: "", cdgroup: "", scriptsizemultiplier: 1 / Math.sqrt(2), scriptminsize: ".4em", infixlinebreakstyle: "before", lineleading: "100%", linebreakmultchar: "\u2062", indentshift: "auto", indentalign: "auto", indenttarget: "", indentalignfirst: "indentalign", indentshiftfirst: "indentshift", indentalignlast: "indentalign", indentshiftlast: "indentshift" });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mi.js
var MmlMi = class _MmlMi extends AbstractMmlTokenNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.ORD;
  }
  get kind() {
    return "mi";
  }
  setInheritedAttributes(attributes = {}, display = false, level = 0, prime = false) {
    super.setInheritedAttributes(attributes, display, level, prime);
    const text = this.getText();
    if (text.match(_MmlMi.singleCharacter) && !attributes.mathvariant) {
      this.attributes.setInherited("mathvariant", "italic");
    }
  }
  setTeXclass(prev) {
    this.getPrevClass(prev);
    const name = this.getText();
    if (name.length > 1 && name.match(_MmlMi.operatorName) && this.attributes.get("mathvariant") === "normal" && this.getProperty("autoOP") === void 0 && this.getProperty("texClass") === void 0) {
      this.texClass = TEXCLASS.OP;
      this.setProperty("autoOP", true);
    }
    return this;
  }
};
MmlMi.defaults = Object.assign({}, AbstractMmlTokenNode.defaults);
MmlMi.operatorName = /^[a-z][a-z0-9]*$/i;
MmlMi.singleCharacter = /^[\uD800-\uDBFF]?.[\u0300-\u036F\u1AB0-\u1ABE\u1DC0-\u1DFF\u20D0-\u20EF]*$/;

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mn.js
var MmlMn = class extends AbstractMmlTokenNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.ORD;
  }
  get kind() {
    return "mn";
  }
};
MmlMn.defaults = Object.assign({}, AbstractMmlTokenNode.defaults);

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mtext.js
var MmlMtext = class _MmlMtext extends AbstractMmlTokenNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.ORD;
  }
  get kind() {
    return "mtext";
  }
  get isSpacelike() {
    return !!this.getText().match(/^\s*$/) && !this.attributes.hasOneOf(_MmlMtext.NONSPACELIKE);
  }
};
MmlMtext.NONSPACELIKE = ["style", "mathbackground", "background"];
MmlMtext.defaults = Object.assign({}, AbstractMmlTokenNode.defaults);

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mspace.js
var MmlMspace = class _MmlMspace extends AbstractMmlTokenNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.NONE;
  }
  setTeXclass(prev) {
    return prev;
  }
  get kind() {
    return "mspace";
  }
  get arity() {
    return 0;
  }
  get isSpacelike() {
    return !this.attributes.hasExplicit("linebreak") && this.canBreak;
  }
  get hasNewline() {
    const linebreak = this.attributes.get("linebreak");
    return this.canBreak && (linebreak === "newline" || linebreak === "indentingnewline");
  }
  get canBreak() {
    return !this.attributes.hasOneOf(_MmlMspace.NONSPACELIKE) && String(this.attributes.get("width")).trim().charAt(0) !== "-";
  }
};
MmlMspace.NONSPACELIKE = [
  "height",
  "depth",
  "style",
  "mathbackground",
  "background"
];
MmlMspace.defaults = Object.assign(Object.assign({}, AbstractMmlTokenNode.defaults), { width: "0em", height: "0ex", depth: "0ex", linebreak: "auto", indentshift: "auto", indentalign: "auto", indenttarget: "", indentalignfirst: "indentalign", indentshiftfirst: "indentshift", indentalignlast: "indentalign", indentshiftlast: "indentshift" });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/ms.js
var MmlMs = class extends AbstractMmlTokenNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.ORD;
  }
  get kind() {
    return "ms";
  }
};
MmlMs.defaults = Object.assign(Object.assign({}, AbstractMmlTokenNode.defaults), { lquote: '"', rquote: '"' });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mrow.js
var MmlMrow = class extends AbstractMmlNode {
  constructor() {
    super(...arguments);
    this._core = null;
  }
  get kind() {
    return "mrow";
  }
  get isSpacelike() {
    for (const child of this.childNodes) {
      if (!child.isSpacelike) {
        return false;
      }
    }
    return true;
  }
  get isEmbellished() {
    let embellished = false;
    let i = 0;
    for (const child of this.childNodes) {
      if (child) {
        if (child.isEmbellished) {
          if (embellished) {
            return false;
          }
          embellished = true;
          this._core = i;
        } else if (!child.isSpacelike) {
          return false;
        }
      }
      i++;
    }
    return embellished;
  }
  core() {
    if (!this.isEmbellished || this._core == null) {
      return this;
    }
    return this.childNodes[this._core];
  }
  coreMO() {
    if (!this.isEmbellished || this._core == null) {
      return this;
    }
    return this.childNodes[this._core].coreMO();
  }
  nonSpaceLength() {
    let n = 0;
    for (const child of this.childNodes) {
      if (child && !child.isSpacelike) {
        n++;
      }
    }
    return n;
  }
  firstNonSpace() {
    for (const child of this.childNodes) {
      if (child && !child.isSpacelike) {
        return child;
      }
    }
    return null;
  }
  lastNonSpace() {
    let i = this.childNodes.length;
    while (--i >= 0) {
      const child = this.childNodes[i];
      if (child && !child.isSpacelike) {
        return child;
      }
    }
    return null;
  }
  setTeXclass(prev) {
    if (this.getProperty("open") != null || this.getProperty("close") != null) {
      this.getPrevClass(prev);
      prev = null;
      for (const child of this.childNodes) {
        prev = child.setTeXclass(prev);
      }
      if (this.texClass == null) {
        this.texClass = TEXCLASS.INNER;
      }
      return this;
    }
    for (const child of this.childNodes) {
      prev = child.setTeXclass(prev);
    }
    if (this.childNodes[0]) {
      this.updateTeXclass(this.childNodes[0]);
    }
    return prev;
  }
};
MmlMrow.defaults = Object.assign({}, AbstractMmlNode.defaults);
var MmlInferredMrow = class extends MmlMrow {
  get kind() {
    return "inferredMrow";
  }
  get isInferred() {
    return true;
  }
  get notParent() {
    return true;
  }
  toString() {
    return "[" + this.childNodes.join(",") + "]";
  }
};
MmlInferredMrow.defaults = MmlMrow.defaults;

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mfrac.js
var MmlMfrac = class extends AbstractMmlBaseNode {
  get kind() {
    return "mfrac";
  }
  get arity() {
    return 2;
  }
  get linebreakContainer() {
    return true;
  }
  get linebreakAlign() {
    return "";
  }
  setTeXclass(prev) {
    this.getPrevClass(prev);
    for (const child of this.childNodes) {
      child.setTeXclass(null);
    }
    return this;
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    if (!display || level > 0) {
      level++;
    }
    const numalign = this.attributes.get("numalign");
    const denalign = this.attributes.get("denomalign");
    const numAttributes = this.addInheritedAttributes(Object.assign({}, attributes), {
      numalign,
      indentshift: "0",
      indentalignfirst: numalign,
      indentshiftfirst: "0",
      indentalignlast: "indentalign",
      indentshiftlast: "indentshift"
    });
    const denAttributes = this.addInheritedAttributes(Object.assign({}, attributes), {
      denalign,
      indentshift: "0",
      indentalignfirst: denalign,
      indentshiftfirst: "0",
      indentalignlast: "indentalign",
      indentshiftlast: "indentshift"
    });
    this.childNodes[0].setInheritedAttributes(numAttributes, false, level, prime);
    this.childNodes[1].setInheritedAttributes(denAttributes, false, level, true);
  }
};
MmlMfrac.defaults = Object.assign(Object.assign({}, AbstractMmlBaseNode.defaults), { linethickness: "medium", numalign: "center", denomalign: "center", bevelled: false });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/msqrt.js
var MmlMsqrt = class extends AbstractMmlNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.ORD;
  }
  get kind() {
    return "msqrt";
  }
  get arity() {
    return -1;
  }
  get linebreakContainer() {
    return true;
  }
  setTeXclass(prev) {
    this.getPrevClass(prev);
    this.childNodes[0].setTeXclass(null);
    return this;
  }
  setChildInheritedAttributes(attributes, display, level, _prime) {
    this.childNodes[0].setInheritedAttributes(attributes, display, level, true);
  }
};
MmlMsqrt.defaults = Object.assign(Object.assign({}, AbstractMmlNode.defaults), { "data-vertical-align": "bottom" });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mroot.js
var MmlMroot = class extends AbstractMmlNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.ORD;
  }
  get kind() {
    return "mroot";
  }
  get arity() {
    return 2;
  }
  get linebreakContainer() {
    return true;
  }
  setTeXclass(prev) {
    this.getPrevClass(prev);
    this.childNodes[0].setTeXclass(null);
    this.childNodes[1].setTeXclass(null);
    return this;
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    this.childNodes[0].setInheritedAttributes(attributes, display, level, true);
    this.childNodes[1].setInheritedAttributes(attributes, false, level + 2, prime);
  }
};
MmlMroot.defaults = Object.assign(Object.assign({}, AbstractMmlNode.defaults), { "data-vertical-align": "bottom" });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mstyle.js
var MmlMstyle = class extends AbstractMmlLayoutNode {
  get kind() {
    return "mstyle";
  }
  get notParent() {
    return this.childNodes[0] && this.childNodes[0].childNodes.length === 1;
  }
  setInheritedAttributes(attributes = {}, display = false, level = 0, prime = false) {
    this.attributes.setInherited("displaystyle", display);
    this.attributes.setInherited("scriptlevel", level);
    super.setInheritedAttributes(attributes, display, level, prime);
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    let scriptlevel = this.attributes.getExplicit("scriptlevel");
    if (scriptlevel != null) {
      scriptlevel = scriptlevel.toString();
      if (scriptlevel.match(/^\s*[-+]/)) {
        level += parseInt(scriptlevel);
      } else {
        level = parseInt(scriptlevel);
      }
      prime = false;
    }
    const displaystyle = this.attributes.getExplicit("displaystyle");
    if (displaystyle != null) {
      display = displaystyle === true;
      prime = false;
    }
    const cramped = this.attributes.getExplicit("data-cramped");
    if (cramped != null) {
      prime = cramped;
    }
    attributes = this.addInheritedAttributes(attributes, this.attributes.getAllAttributes());
    this.childNodes[0].setInheritedAttributes(attributes, display, level, prime);
  }
};
MmlMstyle.defaults = Object.assign(Object.assign({}, AbstractMmlLayoutNode.defaults), { scriptlevel: INHERIT, displaystyle: INHERIT, scriptsizemultiplier: 1 / Math.sqrt(2), scriptminsize: ".4em", mathbackground: INHERIT, mathcolor: INHERIT, dir: INHERIT, infixlinebreakstyle: "before" });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/merror.js
var MmlMerror = class extends AbstractMmlNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.ORD;
  }
  get kind() {
    return "merror";
  }
  get arity() {
    return -1;
  }
  get linebreakContainer() {
    return true;
  }
};
MmlMerror.defaults = Object.assign({}, AbstractMmlNode.defaults);

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mpadded.js
var MmlMpadded = class extends AbstractMmlLayoutNode {
  get kind() {
    return "mpadded";
  }
  get linebreakContainer() {
    return true;
  }
  setTeXclass(prev) {
    if (!this.getProperty("vbox")) {
      return super.setTeXclass(prev);
    }
    this.getPrevClass(prev);
    this.texClass = TEXCLASS.ORD;
    this.childNodes[0].setTeXclass(null);
    return this;
  }
};
MmlMpadded.defaults = Object.assign(Object.assign({}, AbstractMmlLayoutNode.defaults), { width: "", height: "", depth: "", lspace: 0, voffset: 0 });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mphantom.js
var MmlMphantom = class extends AbstractMmlLayoutNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.ORD;
  }
  get kind() {
    return "mphantom";
  }
};
MmlMphantom.defaults = Object.assign({}, AbstractMmlLayoutNode.defaults);

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mfenced.js
var MmlMfenced = class extends AbstractMmlNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.INNER;
    this.separators = [];
    this.open = null;
    this.close = null;
  }
  get kind() {
    return "mfenced";
  }
  setTeXclass(prev) {
    this.getPrevClass(prev);
    if (this.open) {
      prev = this.open.setTeXclass(prev);
    }
    if (this.childNodes[0]) {
      prev = this.childNodes[0].setTeXclass(prev);
    }
    for (let i = 1, m = this.childNodes.length; i < m; i++) {
      if (this.separators[i - 1]) {
        prev = this.separators[i - 1].setTeXclass(prev);
      }
      if (this.childNodes[i]) {
        prev = this.childNodes[i].setTeXclass(prev);
      }
    }
    if (this.close) {
      prev = this.close.setTeXclass(prev);
    }
    if (!this.open || !this.close) {
      this.updateTeXclass(this.open || this.childNodes[0] || this.close);
    }
    return prev;
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    this.addFakeNodes();
    for (const child of [this.open, this.close].concat(this.separators)) {
      if (child) {
        child.setInheritedAttributes(attributes, display, level, prime);
      }
    }
    super.setChildInheritedAttributes(attributes, display, level, prime);
  }
  addFakeNodes() {
    let { open, close, separators } = this.attributes.getList("open", "close", "separators");
    open = open.replace(/[ \t\n\r]/g, "");
    close = close.replace(/[ \t\n\r]/g, "");
    separators = separators.replace(/[ \t\n\r]/g, "");
    if (open) {
      this.open = this.fakeNode(open, { fence: true, form: "prefix" }, TEXCLASS.OPEN);
    }
    if (separators) {
      while (separators.length < this.childNodes.length - 1) {
        separators += separators.charAt(separators.length - 1);
      }
      let i = 0;
      for (const child of this.childNodes.slice(1)) {
        if (child) {
          this.separators.push(this.fakeNode(separators.charAt(i++)));
        }
      }
    }
    if (close) {
      this.close = this.fakeNode(close, { fence: true, form: "postfix" }, TEXCLASS.CLOSE);
    }
  }
  fakeNode(c, properties = {}, texClass = null) {
    const text = this.factory.create("text").setText(c);
    const node = this.factory.create("mo", properties, [text]);
    node.texClass = texClass;
    node.parent = this;
    return node;
  }
};
MmlMfenced.defaults = Object.assign(Object.assign({}, AbstractMmlNode.defaults), { open: "(", close: ")", separators: "," });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/menclose.js
var MmlMenclose = class extends AbstractMmlNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.ORD;
  }
  get kind() {
    return "menclose";
  }
  get arity() {
    return -1;
  }
  get linebreakContainer() {
    return true;
  }
  setTeXclass(prev) {
    prev = this.childNodes[0].setTeXclass(prev);
    this.updateTeXclass(this.childNodes[0]);
    return prev;
  }
};
MmlMenclose.defaults = Object.assign(Object.assign({}, AbstractMmlNode.defaults), { notation: "longdiv" });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/maction.js
var MmlMaction = class extends AbstractMmlNode {
  get kind() {
    return "maction";
  }
  get arity() {
    return 1;
  }
  get selected() {
    const selection = this.attributes.get("selection");
    const i = Math.max(1, Math.min(this.childNodes.length, selection)) - 1;
    return this.childNodes[i] || this.factory.create("mrow");
  }
  get isEmbellished() {
    return this.selected.isEmbellished;
  }
  get isSpacelike() {
    return this.selected.isSpacelike;
  }
  core() {
    return this.selected.core();
  }
  coreMO() {
    return this.selected.coreMO();
  }
  verifyAttributes(options2) {
    super.verifyAttributes(options2);
    if (this.attributes.get("actiontype") !== "toggle" && this.attributes.hasExplicit("selection")) {
      this.attributes.unset("selection");
    }
  }
  setTeXclass(prev) {
    if (this.attributes.get("actiontype") === "tooltip" && this.childNodes[1]) {
      this.childNodes[1].setTeXclass(null);
    }
    const selected = this.selected;
    prev = selected.setTeXclass(prev);
    this.updateTeXclass(selected);
    return prev;
  }
  nextToggleSelection() {
    let selection = Math.max(1, parseInt(this.attributes.get("selection")) + 1);
    if (selection > this.childNodes.length) {
      selection = 1;
    }
    this.attributes.set("selection", selection);
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    var _a, _b;
    if (this.attributes.get("actiontype").toLowerCase() !== "tooltip") {
      super.setChildInheritedAttributes(attributes, display, level, prime);
      return;
    }
    (_a = this.childNodes[0]) === null || _a === void 0 ? void 0 : _a.setInheritedAttributes(attributes, display, level, prime);
    (_b = this.childNodes[1]) === null || _b === void 0 ? void 0 : _b.setInheritedAttributes(attributes, false, 1, false);
  }
};
MmlMaction.defaults = Object.assign(Object.assign({}, AbstractMmlNode.defaults), { actiontype: "toggle", selection: 1 });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/msubsup.js
var MmlMsubsup = class extends AbstractMmlBaseNode {
  get kind() {
    return "msubsup";
  }
  get arity() {
    return 3;
  }
  get base() {
    return 0;
  }
  get sub() {
    return 1;
  }
  get sup() {
    return 2;
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    const nodes = this.childNodes;
    nodes[0].setInheritedAttributes(attributes, display, level, prime);
    nodes[1].setInheritedAttributes(attributes, false, level + 1, prime || this.sub === 1);
    if (!nodes[2]) {
      return;
    }
    nodes[2].setInheritedAttributes(attributes, false, level + 1, prime || this.sub === 2);
  }
};
MmlMsubsup.defaults = Object.assign(Object.assign({}, AbstractMmlBaseNode.defaults), { subscriptshift: "", superscriptshift: "" });
var MmlMsub = class extends MmlMsubsup {
  get kind() {
    return "msub";
  }
  get arity() {
    return 2;
  }
};
MmlMsub.defaults = Object.assign({}, MmlMsubsup.defaults);
var MmlMsup = class extends MmlMsubsup {
  get kind() {
    return "msup";
  }
  get arity() {
    return 2;
  }
  get sup() {
    return 1;
  }
  get sub() {
    return 2;
  }
};
MmlMsup.defaults = Object.assign({}, MmlMsubsup.defaults);

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/munderover.js
var MmlMunderover = class extends AbstractMmlBaseNode {
  get kind() {
    return "munderover";
  }
  get arity() {
    return 3;
  }
  get base() {
    return 0;
  }
  get under() {
    return 1;
  }
  get over() {
    return 2;
  }
  get linebreakContainer() {
    return true;
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    const nodes = this.childNodes;
    nodes[0].setInheritedAttributes(attributes, display, level, prime || !!nodes[this.over]);
    const force = !!(!display && nodes[0].coreMO().attributes.get("movablelimits"));
    const ACCENTS = this.constructor.ACCENTS;
    nodes[1].setInheritedAttributes(attributes, false, this.getScriptlevel(ACCENTS[1], force, level), prime || this.under === 1);
    this.setInheritedAccent(1, ACCENTS[1], display, level, prime, force);
    if (!nodes[2]) {
      return;
    }
    nodes[2].setInheritedAttributes(attributes, false, this.getScriptlevel(ACCENTS[2], force, level), prime || this.under === 2);
    this.setInheritedAccent(2, ACCENTS[2], display, level, prime, force);
  }
  getScriptlevel(accent, force, level) {
    if (force || !this.attributes.get(accent)) {
      level++;
    }
    return level;
  }
  setInheritedAccent(n, accent, display, level, prime, force) {
    const node = this.childNodes[n];
    if (!this.attributes.hasExplicit(accent) && node.isEmbellished) {
      const value = node.coreMO().attributes.get("accent");
      this.attributes.setInherited(accent, value);
      if (value !== this.attributes.getDefault(accent)) {
        node.setInheritedAttributes({}, display, this.getScriptlevel(accent, force, level), prime);
      }
    }
  }
};
MmlMunderover.defaults = Object.assign(Object.assign({}, AbstractMmlBaseNode.defaults), { accent: false, accentunder: false, align: "center" });
MmlMunderover.ACCENTS = ["", "accentunder", "accent"];
var MmlMunder = class extends MmlMunderover {
  get kind() {
    return "munder";
  }
  get arity() {
    return 2;
  }
};
MmlMunder.defaults = Object.assign({}, MmlMunderover.defaults);
var MmlMover = class extends MmlMunderover {
  get kind() {
    return "mover";
  }
  get arity() {
    return 2;
  }
  get over() {
    return 1;
  }
  get under() {
    return 2;
  }
};
MmlMover.defaults = Object.assign({}, MmlMunderover.defaults);
MmlMover.ACCENTS = ["", "accent", "accentunder"];

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mmultiscripts.js
var MmlMmultiscripts = class extends MmlMsubsup {
  get kind() {
    return "mmultiscripts";
  }
  get arity() {
    return 1;
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    this.childNodes[0].setInheritedAttributes(attributes, display, level, prime);
    let prescripts = false;
    for (let i = 1, n = 0; i < this.childNodes.length; i++) {
      const child = this.childNodes[i];
      if (child.isKind("mprescripts")) {
        if (!prescripts) {
          prescripts = true;
          if (i % 2 === 0) {
            const none = this.factory.create("none");
            this.childNodes.splice(i, 0, none);
            none.parent = this;
            i++;
          }
        }
      } else {
        const primestyle = prime || n % 2 === 0;
        child.setInheritedAttributes(attributes, false, level + 1, primestyle);
        n++;
      }
    }
    if (this.childNodes.length % 2 === (prescripts ? 1 : 0)) {
      this.appendChild(this.factory.create("none"));
      this.childNodes[this.childNodes.length - 1].setInheritedAttributes(attributes, false, level + 1, prime);
    }
  }
  verifyChildren(options2) {
    let prescripts = false;
    const fix = options2["fixMmultiscripts"];
    for (let i = 0; i < this.childNodes.length; i++) {
      const child = this.childNodes[i];
      if (child.isKind("mprescripts")) {
        if (prescripts) {
          child.mError(child.kind + " can only appear once in " + this.kind, options2, true);
        } else {
          prescripts = true;
          if (i % 2 === 0 && !fix) {
            this.mError("There must be an equal number of prescripts of each type", options2);
          }
        }
      }
    }
    if (this.childNodes.length % 2 === (prescripts ? 1 : 0) && !fix) {
      this.mError("There must be an equal number of scripts of each type", options2);
    }
    super.verifyChildren(options2);
  }
};
MmlMmultiscripts.defaults = Object.assign({}, MmlMsubsup.defaults);
var MmlMprescripts = class extends AbstractMmlNode {
  get kind() {
    return "mprescripts";
  }
  get arity() {
    return 0;
  }
  verifyTree(options2) {
    super.verifyTree(options2);
    if (this.parent && !this.parent.isKind("mmultiscripts")) {
      this.mError(this.kind + " must be a child of mmultiscripts", options2, true);
    }
  }
};
MmlMprescripts.defaults = Object.assign({}, AbstractMmlNode.defaults);
var MmlNone = class extends AbstractMmlNode {
  get kind() {
    return "none";
  }
  get arity() {
    return 0;
  }
  verifyTree(options2) {
    super.verifyTree(options2);
    if (this.parent && !this.parent.isKind("mmultiscripts")) {
      this.mError(this.kind + " must be a child of mmultiscripts", options2, true);
    }
  }
};
MmlNone.defaults = Object.assign({}, AbstractMmlNode.defaults);

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mtable.js
var MmlMtable = class extends AbstractMmlNode {
  constructor() {
    super(...arguments);
    this.properties = {
      useHeight: true
    };
    this.texclass = TEXCLASS.ORD;
  }
  get kind() {
    return "mtable";
  }
  get linebreakContainer() {
    return true;
  }
  get linebreakAlign() {
    return "";
  }
  setInheritedAttributes(attributes, display, level, prime) {
    for (const name of indentAttributes) {
      if (attributes[name]) {
        this.attributes.setInherited(name, attributes[name][1]);
      }
      if (this.attributes.hasExplicit(name)) {
        this.attributes.unset(name);
      }
    }
    super.setInheritedAttributes(attributes, display, level, prime);
  }
  setChildInheritedAttributes(attributes, display, level, _prime) {
    for (const child of this.childNodes) {
      if (!child.isKind("mtr")) {
        this.replaceChild(this.factory.create("mtr"), child).appendChild(child);
      }
    }
    display = !!(this.attributes.getExplicit("displaystyle") || this.attributes.getDefault("displaystyle"));
    attributes = this.addInheritedAttributes(attributes, {
      columnalign: this.attributes.get("columnalign"),
      rowalign: "center",
      "data-break-align": this.attributes.get("data-break-align")
    });
    const cramped = this.attributes.getExplicit("data-cramped");
    const ralign = split(this.attributes.get("rowalign"));
    for (const child of this.childNodes) {
      attributes.rowalign[1] = ralign.shift() || attributes.rowalign[1];
      child.setInheritedAttributes(attributes, display, level, !!cramped);
    }
  }
  verifyChildren(options2) {
    let mtr = null;
    const factory = this.factory;
    for (let i = 0; i < this.childNodes.length; i++) {
      const child = this.childNodes[i];
      if (child.isKind("mtr")) {
        mtr = null;
      } else {
        const isMtd = child.isKind("mtd");
        if (mtr) {
          this.removeChild(child);
          i--;
        } else {
          mtr = this.replaceChild(factory.create("mtr"), child);
        }
        mtr.appendChild(isMtd ? child : factory.create("mtd", {}, [child]));
        if (!options2["fixMtables"]) {
          child.parent.removeChild(child);
          child.parent = this;
          if (isMtd) {
            mtr.appendChild(factory.create("mtd"));
          }
          const merror = child.mError("Children of " + this.kind + " must be mtr or mlabeledtr", options2, isMtd);
          mtr.childNodes[mtr.childNodes.length - 1].appendChild(merror);
        }
      }
    }
    super.verifyChildren(options2);
  }
  setTeXclass(prev) {
    this.getPrevClass(prev);
    for (const child of this.childNodes) {
      child.setTeXclass(null);
    }
    return this;
  }
};
MmlMtable.defaults = Object.assign(Object.assign({}, AbstractMmlNode.defaults), { align: "axis", rowalign: "baseline", columnalign: "center", groupalign: "{left}", alignmentscope: true, columnwidth: "auto", width: "auto", rowspacing: "1ex", columnspacing: ".8em", rowlines: "none", columnlines: "none", frame: "none", framespacing: "0.4em 0.5ex", equalrows: false, equalcolumns: false, displaystyle: false, side: "right", minlabelspacing: "0.8em", "data-break-align": "top" });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mtr.js
var MmlMtr = class extends AbstractMmlNode {
  get kind() {
    return "mtr";
  }
  get linebreakContainer() {
    return true;
  }
  get linebreakAlign() {
    return "";
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    for (const child of this.childNodes) {
      if (!child.isKind("mtd")) {
        this.replaceChild(this.factory.create("mtd"), child).appendChild(child);
      }
    }
    const calign = split(this.attributes.get("columnalign"));
    const balign = split(this.attributes.get("data-break-align"));
    if (this.arity === 1) {
      calign.unshift(this.parent.attributes.get("side"));
      balign.unshift("top");
    }
    attributes = this.addInheritedAttributes(attributes, {
      rowalign: this.attributes.get("rowalign"),
      columnalign: "center",
      "data-break-align": "top"
    });
    for (const child of this.childNodes) {
      attributes.columnalign[1] = calign.shift() || attributes.columnalign[1];
      attributes["data-vertical-align"] = [
        this.kind,
        balign.shift() || attributes["data-break-align"][1]
      ];
      child.setInheritedAttributes(attributes, display, level, prime);
    }
  }
  verifyChildren(options2) {
    if (this.parent && !this.parent.isKind("mtable")) {
      this.mError(this.kind + " can only be a child of an mtable", options2, true);
      return;
    }
    for (const child of this.childNodes) {
      if (!child.isKind("mtd")) {
        const mtd = this.replaceChild(this.factory.create("mtd"), child);
        mtd.appendChild(child);
        if (!options2["fixMtables"]) {
          child.mError("Children of " + this.kind + " must be mtd", options2);
        }
      }
    }
    super.verifyChildren(options2);
  }
  setTeXclass(prev) {
    this.getPrevClass(prev);
    for (const child of this.childNodes) {
      child.setTeXclass(null);
    }
    return this;
  }
};
MmlMtr.defaults = Object.assign(Object.assign({}, AbstractMmlNode.defaults), { rowalign: INHERIT, columnalign: INHERIT, groupalign: INHERIT, "data-break-align": "top" });
var MmlMlabeledtr = class extends MmlMtr {
  get kind() {
    return "mlabeledtr";
  }
  get arity() {
    return 1;
  }
};

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mtd.js
var MmlMtd = class extends AbstractMmlBaseNode {
  get kind() {
    return "mtd";
  }
  get arity() {
    return -1;
  }
  get linebreakContainer() {
    return true;
  }
  get linebreakAlign() {
    return "columnalign";
  }
  verifyChildren(options2) {
    if (this.parent && !this.parent.isKind("mtr")) {
      this.mError(this.kind + " can only be a child of an mtr or mlabeledtr", options2, true);
      return;
    }
    super.verifyChildren(options2);
  }
  setTeXclass(prev) {
    this.getPrevClass(prev);
    this.childNodes[0].setTeXclass(null);
    return this;
  }
};
MmlMtd.defaults = Object.assign(Object.assign({}, AbstractMmlBaseNode.defaults), { rowspan: 1, columnspan: 1, rowalign: INHERIT, columnalign: INHERIT, groupalign: INHERIT, "data-vertical-align": "top" });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/maligngroup.js
var MmlMaligngroup = class extends AbstractMmlLayoutNode {
  get kind() {
    return "maligngroup";
  }
  get isSpacelike() {
    return true;
  }
  setChildInheritedAttributes(attributes, display, level, prime) {
    attributes = this.addInheritedAttributes(attributes, this.attributes.getAllAttributes());
    super.setChildInheritedAttributes(attributes, display, level, prime);
  }
};
MmlMaligngroup.defaults = Object.assign(Object.assign({}, AbstractMmlLayoutNode.defaults), { groupalign: INHERIT });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/malignmark.js
var MmlMalignmark = class extends AbstractMmlNode {
  get kind() {
    return "malignmark";
  }
  get arity() {
    return 0;
  }
  get isSpacelike() {
    return true;
  }
};
MmlMalignmark.defaults = Object.assign(Object.assign({}, AbstractMmlNode.defaults), { edge: "left" });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mglyph.js
var MmlMglyph = class extends AbstractMmlTokenNode {
  constructor() {
    super(...arguments);
    this.texclass = TEXCLASS.ORD;
  }
  get kind() {
    return "mglyph";
  }
  verifyAttributes(options2) {
    const { src, fontfamily, index } = this.attributes.getList("src", "fontfamily", "index");
    if (src === "" && (fontfamily === "" || index === "")) {
      this.mError("mglyph must have either src or fontfamily and index attributes", options2, true);
    } else {
      super.verifyAttributes(options2);
    }
  }
};
MmlMglyph.defaults = Object.assign(Object.assign({}, AbstractMmlTokenNode.defaults), { alt: "", src: "", index: "", width: "auto", height: "auto", valign: "0em" });

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/semantics.js
var MmlSemantics = class extends AbstractMmlBaseNode {
  get kind() {
    return "semantics";
  }
  get arity() {
    return 1;
  }
  get notParent() {
    return true;
  }
};
MmlSemantics.defaults = Object.assign(Object.assign({}, AbstractMmlBaseNode.defaults), { definitionUrl: null, encoding: null });
var MmlAnnotationXML = class extends AbstractMmlNode {
  get kind() {
    return "annotation-xml";
  }
  setChildInheritedAttributes() {
  }
};
MmlAnnotationXML.defaults = Object.assign(Object.assign({}, AbstractMmlNode.defaults), { definitionUrl: null, encoding: null, cd: "mathmlkeys", name: "", src: null });
var MmlAnnotation = class extends MmlAnnotationXML {
  constructor() {
    super(...arguments);
    this.properties = {
      isChars: true
    };
  }
  get kind() {
    return "annotation";
  }
};
MmlAnnotation.defaults = Object.assign({}, MmlAnnotationXML.defaults);

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/TeXAtom.js
var TeXAtom = class extends AbstractMmlBaseNode {
  get kind() {
    return "TeXAtom";
  }
  get arity() {
    return -1;
  }
  get notParent() {
    return true;
  }
  constructor(factory, attributes, children) {
    super(factory, attributes, children);
    this.texclass = TEXCLASS.ORD;
    this.setProperty("texClass", this.texClass);
  }
  setTeXclass(prev) {
    this.childNodes[0].setTeXclass(null);
    return this.adjustTeXclass(prev);
  }
  adjustTeXclass(prev) {
    return prev;
  }
};
TeXAtom.defaults = Object.assign({}, AbstractMmlBaseNode.defaults);
TeXAtom.prototype.adjustTeXclass = MmlMo.prototype.adjustTeXclass;

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/mathchoice.js
var MathChoice = class extends AbstractMmlBaseNode {
  get kind() {
    return "MathChoice";
  }
  get arity() {
    return 4;
  }
  get notParent() {
    return true;
  }
  setInheritedAttributes(attributes, display, level, prime) {
    const selection = display ? 0 : Math.max(0, Math.min(level, 2)) + 1;
    const child = this.childNodes[selection] || this.factory.create("mrow");
    this.parent.replaceChild(child, this);
    child.setInheritedAttributes(attributes, display, level, prime);
  }
};
MathChoice.defaults = Object.assign({}, AbstractMmlBaseNode.defaults);

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlNodes/HtmlNode.js
var HtmlNode = class extends XMLNode {
  get kind() {
    return "html";
  }
  getHTML() {
    return this.getXML();
  }
  setHTML(html, adaptor2 = null) {
    try {
      adaptor2.getAttribute(html, "data-mjx-hdw");
    } catch (_error) {
      html = adaptor2.node("span", {}, [html]);
    }
    return this.setXML(html, adaptor2);
  }
  getSerializedHTML() {
    return this.adaptor.outerHTML(this.xml);
  }
  textContent() {
    return this.adaptor.textContent(this.xml);
  }
  toString() {
    const kind = this.adaptor.kind(this.xml);
    return `HTML=<${kind}>...</${kind}>`;
  }
  verifyTree(options2) {
    if (this.parent && !this.parent.isToken) {
      this.mError("HTML can only be a child of a token element", options2, true);
      return;
    }
  }
};

// node_modules/@mathjax/src/mjs/core/MmlTree/MML.js
var MML = {
  [MmlMath.prototype.kind]: MmlMath,
  [MmlMi.prototype.kind]: MmlMi,
  [MmlMn.prototype.kind]: MmlMn,
  [MmlMo.prototype.kind]: MmlMo,
  [MmlMtext.prototype.kind]: MmlMtext,
  [MmlMspace.prototype.kind]: MmlMspace,
  [MmlMs.prototype.kind]: MmlMs,
  [MmlMrow.prototype.kind]: MmlMrow,
  [MmlInferredMrow.prototype.kind]: MmlInferredMrow,
  [MmlMfrac.prototype.kind]: MmlMfrac,
  [MmlMsqrt.prototype.kind]: MmlMsqrt,
  [MmlMroot.prototype.kind]: MmlMroot,
  [MmlMstyle.prototype.kind]: MmlMstyle,
  [MmlMerror.prototype.kind]: MmlMerror,
  [MmlMpadded.prototype.kind]: MmlMpadded,
  [MmlMphantom.prototype.kind]: MmlMphantom,
  [MmlMfenced.prototype.kind]: MmlMfenced,
  [MmlMenclose.prototype.kind]: MmlMenclose,
  [MmlMaction.prototype.kind]: MmlMaction,
  [MmlMsub.prototype.kind]: MmlMsub,
  [MmlMsup.prototype.kind]: MmlMsup,
  [MmlMsubsup.prototype.kind]: MmlMsubsup,
  [MmlMunder.prototype.kind]: MmlMunder,
  [MmlMover.prototype.kind]: MmlMover,
  [MmlMunderover.prototype.kind]: MmlMunderover,
  [MmlMmultiscripts.prototype.kind]: MmlMmultiscripts,
  [MmlMprescripts.prototype.kind]: MmlMprescripts,
  [MmlNone.prototype.kind]: MmlNone,
  [MmlMtable.prototype.kind]: MmlMtable,
  [MmlMlabeledtr.prototype.kind]: MmlMlabeledtr,
  [MmlMtr.prototype.kind]: MmlMtr,
  [MmlMtd.prototype.kind]: MmlMtd,
  [MmlMaligngroup.prototype.kind]: MmlMaligngroup,
  [MmlMalignmark.prototype.kind]: MmlMalignmark,
  [MmlMglyph.prototype.kind]: MmlMglyph,
  [MmlSemantics.prototype.kind]: MmlSemantics,
  [MmlAnnotation.prototype.kind]: MmlAnnotation,
  [MmlAnnotationXML.prototype.kind]: MmlAnnotationXML,
  [TeXAtom.prototype.kind]: TeXAtom,
  [MathChoice.prototype.kind]: MathChoice,
  [TextNode.prototype.kind]: TextNode,
  [XMLNode.prototype.kind]: XMLNode,
  [HtmlNode.prototype.kind]: HtmlNode
};

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlFactory.js
var MmlFactory = class extends AbstractNodeFactory {
  get MML() {
    return this.node;
  }
};
MmlFactory.defaultNodes = MML;

// node_modules/@mathjax/src/mjs/util/BitField.js
var BitField = class _BitField {
  constructor() {
    this.bits = 0;
  }
  static allocate(...names) {
    for (const name of names) {
      if (this.has(name)) {
        throw new Error("Bit already allocated for " + name);
      }
      if (this.next === _BitField.MAXBIT) {
        throw new Error("Maximum number of bits already allocated");
      }
      this.names.set(name, this.next);
      this.next <<= 1;
    }
  }
  static has(name) {
    return this.names.has(name);
  }
  set(name) {
    this.bits |= this.getBit(name);
  }
  clear(name) {
    this.bits &= ~this.getBit(name);
  }
  isSet(name) {
    return !!(this.bits & this.getBit(name));
  }
  reset() {
    this.bits = 0;
  }
  getBit(name) {
    const bit = this.constructor.names.get(name);
    if (!bit) {
      throw new Error("Unknown bit-field name: " + name);
    }
    return bit;
  }
};
BitField.MAXBIT = 1 << 31;
BitField.next = 1;
BitField.names = /* @__PURE__ */ new Map();
function BitFieldClass(...names) {
  const bits = class extends BitField {
  };
  bits.allocate(...names);
  return bits;
}

// node_modules/@mathjax/src/mjs/core/MathDocument.js
var __awaiter3 = function(thisArg, _arguments, P, generator) {
  function adopt(value) {
    return value instanceof P ? value : new P(function(resolve) {
      resolve(value);
    });
  }
  return new (P || (P = Promise))(function(resolve, reject) {
    function fulfilled(value) {
      try {
        step(generator.next(value));
      } catch (e) {
        reject(e);
      }
    }
    function rejected(value) {
      try {
        step(generator["throw"](value));
      } catch (e) {
        reject(e);
      }
    }
    function step(result) {
      result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
    }
    step((generator = generator.apply(thisArg, _arguments || [])).next());
  });
};
var RenderList = class extends PrioritizedList {
  static create(actions) {
    const list = new this();
    for (const id of Object.keys(actions)) {
      const [action, priority] = this.action(id, actions[id]);
      if (priority) {
        list.add(action, priority);
      }
    }
    return list;
  }
  static action(id, action) {
    let renderDoc, renderMath;
    let convert = true;
    const priority = action[0];
    if (action.length === 1 || typeof action[1] === "boolean") {
      if (action.length === 2) {
        convert = action[1];
      }
      [renderDoc, renderMath] = this.methodActions(id);
    } else if (typeof action[1] === "string") {
      if (typeof action[2] === "string") {
        if (action.length === 4) {
          convert = action[3];
        }
        const [method1, method2] = action.slice(1);
        [renderDoc, renderMath] = this.methodActions(method1, method2);
      } else {
        if (action.length === 3) {
          convert = action[2];
        }
        [renderDoc, renderMath] = this.methodActions(action[1]);
      }
    } else {
      if (action.length === 4) {
        convert = action[3];
      }
      [renderDoc, renderMath] = action.slice(1);
    }
    return [
      { id, renderDoc, renderMath, convert },
      priority
    ];
  }
  static methodActions(method1, method2 = method1) {
    return [
      (document2) => {
        if (method1) {
          document2[method1]();
        }
        return false;
      },
      (math, document2) => {
        if (method2) {
          math[method2](document2);
        }
        return false;
      }
    ];
  }
  renderDoc(document2, start = STATE.UNPROCESSED) {
    for (const item of this.items) {
      if (item.priority >= start) {
        if (item.item.renderDoc(document2))
          return;
      }
    }
  }
  renderMath(math, document2, start = STATE.UNPROCESSED) {
    for (const item of this.items) {
      if (item.priority >= start) {
        if (item.item.renderMath(math, document2))
          return;
      }
    }
  }
  renderConvert(math, document2, end = STATE.LAST) {
    for (const item of this.items) {
      if (item.priority > end)
        return;
      if (item.item.convert) {
        if (item.item.renderMath(math, document2))
          return;
      }
    }
  }
  findID(id) {
    for (const item of this.items) {
      if (item.item.id === id) {
        return item.item;
      }
    }
    return null;
  }
};
var resetOptions = {
  all: false,
  processed: false,
  inputJax: null,
  outputJax: null
};
var resetAllOptions = {
  all: true,
  processed: true,
  inputJax: [],
  outputJax: []
};
var DefaultInputJax = class extends AbstractInputJax {
  compile(_math) {
    return null;
  }
};
var DefaultOutputJax = class extends AbstractOutputJax {
  typeset(_math, _document = null) {
    return null;
  }
  escaped(_math, _document) {
    return null;
  }
};
var DefaultMathList = class extends AbstractMathList {
};
var DefaultMathItem = class extends AbstractMathItem {
};
var AbstractMathDocument = class _AbstractMathDocument {
  constructor(document2, adaptor2, options2) {
    const CLASS = this.constructor;
    this.document = document2;
    this.options = userOptions(defaultOptions({}, CLASS.OPTIONS), options2);
    this.math = new (this.options["MathList"] || DefaultMathList)();
    this.renderActions = RenderList.create(this.options["renderActions"]);
    this._actionPromises = [];
    this._readyPromise = Promise.resolve();
    this.processed = new _AbstractMathDocument.ProcessBits();
    this.outputJax = this.options["OutputJax"] || new DefaultOutputJax();
    let inputJax = this.options["InputJax"] || [new DefaultInputJax()];
    if (!Array.isArray(inputJax)) {
      inputJax = [inputJax];
    }
    this.inputJax = inputJax;
    this.adaptor = adaptor2;
    this.outputJax.setAdaptor(adaptor2);
    this.inputJax.map((jax) => jax.setAdaptor(adaptor2));
    this.mmlFactory = this.options["MmlFactory"] || new MmlFactory();
    this.inputJax.map((jax) => jax.setMmlFactory(this.mmlFactory));
    this.outputJax.initialize();
    this.inputJax.map((jax) => jax.initialize());
  }
  get kind() {
    return this.constructor.KIND;
  }
  addRenderAction(id, ...action) {
    const [fn, p] = RenderList.action(id, action);
    this.renderActions.add(fn, p);
  }
  removeRenderAction(id) {
    const action = this.renderActions.findID(id);
    if (action) {
      this.renderActions.remove(action);
    }
  }
  render() {
    this.clearPromises();
    this.renderActions.renderDoc(this);
    return this;
  }
  renderPromise() {
    return this.whenReady(() => handleRetriesFor(() => __awaiter3(this, void 0, void 0, function* () {
      this.render();
      yield this.actionPromises();
      this.clearPromises();
      return this;
    })));
  }
  rerender(start = STATE.RERENDER) {
    this.state(start - 1);
    this.render();
    return this;
  }
  rerenderPromise(start = STATE.RERENDER) {
    return this.whenReady(() => handleRetriesFor(() => __awaiter3(this, void 0, void 0, function* () {
      this.rerender(start);
      yield this.actionPromises();
      this.clearPromises();
      return this;
    })));
  }
  convert(math, options2 = {}) {
    let { format, display, end, ex, em: em2, containerWidth, scale, family } = userOptions({
      format: this.inputJax[0].name,
      display: true,
      end: STATE.LAST,
      em: 16,
      ex: 8,
      containerWidth: null,
      scale: 1,
      family: ""
    }, options2);
    if (containerWidth === null) {
      containerWidth = 80 * ex;
    }
    const jax = this.inputJax.reduce((jax2, ijax) => ijax.name === format ? ijax : jax2, null);
    const mitem = new this.options.MathItem(math, jax, display);
    mitem.start.node = this.adaptor.body(this.document);
    mitem.setMetrics(em2, ex, containerWidth, scale);
    if (family && this.outputJax.options.mtextInheritFont) {
      mitem.outputData.mtextFamily = family;
    }
    if (family && this.outputJax.options.merrorInheritFont) {
      mitem.outputData.merrorFamily = family;
    }
    this.clearPromises();
    mitem.convert(this, end);
    return mitem.typesetRoot || mitem.root;
  }
  convertPromise(math, options2 = {}) {
    return this.whenReady(() => handleRetriesFor(() => __awaiter3(this, void 0, void 0, function* () {
      const node = this.convert(math, options2);
      yield this.actionPromises();
      this.clearPromises();
      return node;
    })));
  }
  whenReady(action) {
    return this._readyPromise = this._readyPromise.catch((_) => {
    }).then(() => {
      const ready = this._readyPromise;
      this._readyPromise = Promise.resolve();
      const result = action();
      const promise = this._readyPromise.then(() => result);
      this._readyPromise = ready;
      return promise;
    });
  }
  actionPromises() {
    return Promise.all(this._actionPromises);
  }
  clearPromises() {
    this._actionPromises = [];
  }
  savePromise(promise) {
    this._actionPromises.push(promise);
  }
  findMath(_options = null) {
    this.processed.set("findMath");
    return this;
  }
  compile() {
    if (!this.processed.isSet("compile")) {
      const recompile = [];
      for (const math of this.math) {
        this.compileMath(math);
        if (math.inputData.recompile !== void 0) {
          recompile.push(math);
        }
      }
      for (const math of recompile) {
        const data = math.inputData.recompile;
        math.state(data.state);
        math.inputData.recompile = data;
        this.compileMath(math);
      }
      this.processed.set("compile");
    }
    return this;
  }
  compileMath(math) {
    try {
      math.compile(this);
    } catch (err) {
      if (err.retry || err.restart) {
        throw err;
      }
      this.options["compileError"](this, math, err);
      math.inputData["error"] = err;
    }
  }
  compileError(math, err) {
    math.root = this.mmlFactory.create("math", null, [
      this.mmlFactory.create("merror", { "data-mjx-error": err.message, title: err.message }, [
        this.mmlFactory.create("mtext", null, [
          this.mmlFactory.create("text").setText("Math input error")
        ])
      ])
    ]);
    if (math.display) {
      math.root.attributes.set("display", "block");
    }
    math.inputData.error = err.message;
  }
  typeset() {
    if (!this.processed.isSet("typeset")) {
      for (const math of this.math) {
        try {
          math.typeset(this);
        } catch (err) {
          if (err.retry || err.restart) {
            throw err;
          }
          this.options["typesetError"](this, math, err);
          math.outputData["error"] = err;
        }
      }
      this.processed.set("typeset");
    }
    return this;
  }
  typesetError(math, err) {
    math.typesetRoot = this.adaptor.node("mjx-container", {
      class: "MathJax mjx-output-error",
      jax: this.outputJax.name
    }, [
      this.adaptor.node("span", {
        "data-mjx-error": err.message,
        title: err.message,
        style: {
          color: "red",
          "background-color": "yellow",
          "line-height": "normal"
        }
      }, [this.adaptor.text("Math output error")])
    ]);
    if (math.display) {
      this.adaptor.setAttributes(math.typesetRoot, {
        style: {
          display: "block",
          margin: "1em 0",
          "text-align": "center"
        }
      });
    }
    math.outputData.error = err.message;
  }
  getMetrics() {
    if (!this.processed.isSet("getMetrics")) {
      this.outputJax.getMetrics(this);
      this.processed.set("getMetrics");
    }
    return this;
  }
  updateDocument() {
    if (!this.processed.isSet("updateDocument")) {
      for (const math of this.math.reversed()) {
        math.updateDocument(this);
      }
      this.processed.set("updateDocument");
    }
    return this;
  }
  removeFromDocument(_restore = false) {
    return this;
  }
  state(state, restore = false) {
    for (const math of this.math) {
      math.state(state, restore);
    }
    if (state < STATE.INSERTED) {
      this.processed.clear("updateDocument");
    }
    if (state < STATE.TYPESET) {
      this.processed.clear("typeset");
      this.processed.clear("getMetrics");
    }
    if (state < STATE.COMPILED) {
      this.processed.clear("compile");
    }
    if (state < STATE.FINDMATH) {
      this.processed.clear("findMath");
    }
    return this;
  }
  reset(options2 = { processed: true }) {
    options2 = userOptions(Object.assign({}, resetOptions), options2);
    if (options2.all) {
      Object.assign(options2, resetAllOptions);
    }
    if (options2.processed) {
      this.processed.reset();
    }
    if (options2.inputJax) {
      this.inputJax.forEach((jax) => jax.reset(...options2.inputJax));
    }
    if (options2.outputJax) {
      this.outputJax.reset(...options2.outputJax);
    }
    return this;
  }
  clear() {
    this.reset();
    this.math.clear();
    return this;
  }
  done() {
    return Promise.resolve();
  }
  concat(list) {
    this.math.merge(list);
    return this;
  }
  clearMathItemsWithin(containers) {
    const items = this.getMathItemsWithin(containers);
    for (const item of items.slice(0).reverse()) {
      item.clear();
    }
    this.math.remove(...items);
    return items;
  }
  getMathItemsWithin(elements) {
    if (!Array.isArray(elements)) {
      elements = [elements];
    }
    const adaptor2 = this.adaptor;
    const items = [];
    const containers = adaptor2.getElements(elements, this.document);
    ITEMS: for (const item of this.math) {
      for (const container of containers) {
        if (item.start.node && adaptor2.contains(container, item.start.node)) {
          items.push(item);
          continue ITEMS;
        }
      }
    }
    return items;
  }
};
AbstractMathDocument.KIND = "MathDocument";
AbstractMathDocument.OPTIONS = {
  OutputJax: null,
  InputJax: null,
  MmlFactory: null,
  MathList: DefaultMathList,
  MathItem: DefaultMathItem,
  compileError: (doc, math, err) => {
    doc.compileError(math, err);
  },
  typesetError: (doc, math, err) => {
    doc.typesetError(math, err);
  },
  renderActions: expandable({
    find: [STATE.FINDMATH, "findMath", "", false],
    compile: [STATE.COMPILED],
    metrics: [STATE.METRICS, "getMetrics", "", false],
    typeset: [STATE.TYPESET],
    update: [STATE.INSERTED, "updateDocument", false]
  })
};
AbstractMathDocument.ProcessBits = BitFieldClass("findMath", "compile", "getMetrics", "typeset", "updateDocument");

// node_modules/@mathjax/src/mjs/core/Handler.js
var DefaultMathDocument = class extends AbstractMathDocument {
};
var AbstractHandler = class {
  constructor(adaptor2, priority = 5) {
    this.documentClass = DefaultMathDocument;
    this.adaptor = adaptor2;
    this.priority = priority;
  }
  get name() {
    return this.constructor.NAME;
  }
  handlesDocument(_document) {
    return false;
  }
  create(document2, options2) {
    return new this.documentClass(document2, this.adaptor, options2);
  }
};
AbstractHandler.NAME = "generic";

// node_modules/@mathjax/src/mjs/handlers/html/HTMLMathItem.js
var HTMLMathItem = class extends AbstractMathItem {
  get adaptor() {
    return this.inputJax.adaptor;
  }
  constructor(math, jax, display = true, start = { node: null, n: 0, delim: "" }, end = { node: null, n: 0, delim: "" }) {
    super(math, jax, display, start, end);
  }
  updateDocument(_html) {
    if (this.state() < STATE.INSERTED) {
      if (this.inputJax.processStrings) {
        let node = this.start.node;
        if (node === this.end.node) {
          if (this.end.n && this.end.n < this.adaptor.value(this.end.node).length) {
            this.adaptor.split(this.end.node, this.end.n);
          }
          if (this.start.n) {
            node = this.adaptor.split(this.start.node, this.start.n);
          }
          if (this.adaptor.parent(node)) {
            this.adaptor.replace(this.typesetRoot, node);
          }
        } else {
          if (this.start.n) {
            node = this.adaptor.split(node, this.start.n);
          }
          while (node !== this.end.node) {
            const next = this.adaptor.next(node);
            this.adaptor.remove(node);
            node = next;
          }
          this.adaptor.insert(this.typesetRoot, node);
          if (this.end.n < this.adaptor.value(node).length) {
            this.adaptor.split(node, this.end.n);
          }
          this.adaptor.remove(node);
        }
      } else {
        this.adaptor.replace(this.typesetRoot, this.start.node);
      }
      this.start.node = this.end.node = this.typesetRoot;
      this.start.n = this.end.n = 0;
      this.state(STATE.INSERTED);
    }
  }
  updateStyleSheet(document2) {
    document2.addStyleSheet();
  }
  removeFromDocument(restore = false) {
    super.removeFromDocument(restore);
    if (this.state() >= STATE.TYPESET) {
      const adaptor2 = this.adaptor;
      const node = this.start.node;
      let math = adaptor2.text("");
      if (restore) {
        const text = this.start.delim + this.math + this.end.delim;
        if (this.inputJax.processStrings) {
          math = adaptor2.text(text);
        } else {
          const doc = adaptor2.parse(text, "text/html");
          math = adaptor2.firstChild(adaptor2.body(doc));
        }
      }
      if (adaptor2.parent(node)) {
        adaptor2.replace(math, node);
      }
      this.start.node = this.end.node = math;
      this.start.n = this.end.n = 0;
    }
  }
};

// node_modules/@mathjax/src/mjs/handlers/html/HTMLMathList.js
var HTMLMathList = class extends AbstractMathList {
};

// node_modules/@mathjax/src/mjs/handlers/html/HTMLDomStrings.js
var HTMLDomStrings = class {
  constructor(options2 = null) {
    const CLASS = this.constructor;
    this.options = userOptions(defaultOptions({}, CLASS.OPTIONS), options2);
    this.init();
    this.getPatterns();
  }
  init() {
    this.strings = [];
    this.string = "";
    this.snodes = [];
    this.nodes = [];
    this.stack = [];
  }
  getPatterns() {
    const skip = makeArray(this.options["skipHtmlTags"]);
    const ignore = makeArray(this.options["ignoreHtmlClass"]);
    const process2 = makeArray(this.options["processHtmlClass"]);
    this.skipHtmlTags = new RegExp("^(?:" + skip.join("|") + ")$", "i");
    this.ignoreHtmlClass = new RegExp("(?:^| )(?:" + ignore.join("|") + ")(?: |$)");
    this.processHtmlClass = new RegExp("(?:^| )(?:" + process2 + ")(?: |$)");
  }
  pushString() {
    if (this.string.match(/\S/)) {
      this.strings.push(this.string);
      this.nodes.push(this.snodes);
    }
    this.string = "";
    this.snodes = [];
  }
  extendString(node, text) {
    this.snodes.push([node, text.length]);
    this.string += text;
  }
  handleText(node, ignore) {
    if (!ignore) {
      this.extendString(node, this.adaptor.value(node));
    }
    return this.adaptor.next(node);
  }
  handleTag(node, ignore) {
    if (!ignore) {
      const text = this.options["includeHtmlTags"][this.adaptor.kind(node)];
      if (text instanceof Function) {
        this.extendString(node, text(node, this.adaptor));
      } else {
        this.extendString(node, text);
      }
    }
    return this.adaptor.next(node);
  }
  handleContainer(node, ignore) {
    this.pushString();
    const cname = this.adaptor.getAttribute(node, "class") || "";
    const tname = this.adaptor.kind(node) || "";
    const process2 = this.processHtmlClass.exec(cname);
    let next = node;
    if (this.adaptor.firstChild(node) && !this.adaptor.getAttribute(node, "data-MJX") && (process2 || !this.skipHtmlTags.exec(tname))) {
      if (this.adaptor.next(node)) {
        this.stack.push([this.adaptor.next(node), ignore]);
      }
      next = this.adaptor.firstChild(node);
      ignore = (ignore || this.ignoreHtmlClass.exec(cname)) && !process2;
    } else {
      next = this.adaptor.next(node);
    }
    return [next, ignore];
  }
  handleOther(node, _ignore) {
    this.pushString();
    return this.adaptor.next(node);
  }
  find(node) {
    this.init();
    const stop = this.adaptor.next(node);
    let ignore = false;
    const include = this.options["includeHtmlTags"];
    while (node && node !== stop) {
      const kind = this.adaptor.kind(node);
      if (kind === "#text") {
        node = this.handleText(node, ignore);
      } else if (Object.hasOwn(include, kind)) {
        node = this.handleTag(node, ignore);
      } else if (kind) {
        [node, ignore] = this.handleContainer(node, ignore);
      } else {
        node = this.handleOther(node, ignore);
      }
      if (!node && this.stack.length) {
        this.pushString();
        [node, ignore] = this.stack.pop();
      }
    }
    this.pushString();
    const result = [this.strings, this.nodes];
    this.init();
    return result;
  }
};
HTMLDomStrings.OPTIONS = {
  skipHtmlTags: [
    "script",
    "noscript",
    "style",
    "textarea",
    "pre",
    "code",
    "math",
    "select",
    "option",
    "mjx-container"
  ],
  includeHtmlTags: expandable({ br: "\n", wbr: "", "#comment": "" }),
  ignoreHtmlClass: "mathjax_ignore",
  processHtmlClass: "mathjax_process"
};

// node_modules/@mathjax/src/mjs/handlers/html/HTMLDocument.js
newState("STYLES", STATE.INSERTED + 1);
var HTMLDocument = class extends AbstractMathDocument {
  constructor(document2, adaptor2, options2) {
    const [html, dom] = separateOptions(options2, HTMLDomStrings.OPTIONS);
    super(document2, adaptor2, html);
    this.domStrings = this.options["DomStrings"] || new HTMLDomStrings(dom);
    this.domStrings.adaptor = adaptor2;
    this.styles = [];
  }
  findPosition(N, index, delim, nodes) {
    const adaptor2 = this.adaptor;
    const inc = 1 / (nodes[N].length || 1);
    let i = N;
    for (const [node, n] of nodes[N]) {
      if (index <= n && adaptor2.kind(node) === "#text") {
        return { i, node, n: Math.max(index, 0), delim };
      }
      index -= n;
      i += inc;
    }
    return { node: null, n: 0, delim };
  }
  mathItem(item, jax, nodes) {
    const math = item.math;
    const start = this.findPosition(item.n, item.start.n, item.open, nodes);
    const end = this.findPosition(item.n, item.end.n, item.close, nodes);
    return new this.options.MathItem(math, jax, item.display, start, end);
  }
  findMath(options2) {
    if (!this.processed.isSet("findMath")) {
      this.adaptor.document = this.document;
      options2 = userOptions({
        elements: this.options.elements || [this.adaptor.body(this.document)]
      }, options2);
      const containers = this.adaptor.getElements(options2.elements, this.document);
      for (const jax of this.inputJax) {
        const list = jax.processStrings ? this.findMathFromStrings(jax, containers) : this.findMathFromDOM(jax, containers);
        this.math.merge(list);
      }
      this.processed.set("findMath");
    }
    return this;
  }
  findMathFromStrings(jax, containers) {
    const strings = [];
    const nodes = [];
    for (const container of containers) {
      const [slist, nlist] = this.domStrings.find(container);
      strings.push(...slist);
      nodes.push(...nlist);
    }
    const list = new this.options.MathList();
    for (const math of jax.findMath(strings)) {
      list.push(this.mathItem(math, jax, nodes));
    }
    return list;
  }
  findMathFromDOM(jax, containers) {
    const items = [];
    for (const container of containers) {
      for (const math of jax.findMath(container)) {
        items.push(new this.options.MathItem(math.math, jax, math.display, math.start, math.end));
      }
    }
    return new this.options.MathList(...items);
  }
  updateDocument() {
    if (!this.processed.isSet("updateDocument")) {
      this.addPageElements();
      this.addStyleSheet();
      super.updateDocument();
      this.processed.set("updateDocument");
    }
    return this;
  }
  addPageElements() {
    const adaptor2 = this.adaptor;
    const body = adaptor2.body(this.document);
    const node = this.documentPageElements();
    if (node) {
      const child = adaptor2.firstChild(body);
      if (child) {
        adaptor2.insert(node, child);
      } else {
        adaptor2.append(body, node);
      }
    }
  }
  addStyleSheet() {
    const sheet = this.documentStyleSheet();
    const adaptor2 = this.adaptor;
    if (sheet && !adaptor2.parent(sheet)) {
      const head = adaptor2.head(this.document);
      const styles = this.findSheet(head, adaptor2.getAttribute(sheet, "id"));
      if (styles) {
        adaptor2.replace(sheet, styles);
      } else {
        adaptor2.append(head, sheet);
      }
    }
  }
  findSheet(head, id) {
    if (id) {
      for (const sheet of this.adaptor.tags(head, "style")) {
        if (this.adaptor.getAttribute(sheet, "id") === id) {
          return sheet;
        }
      }
    }
    return null;
  }
  removeFromDocument(restore = false) {
    if (this.processed.isSet("updateDocument")) {
      for (const math of this.math) {
        if (math.state() >= STATE.INSERTED) {
          math.state(STATE.TYPESET, restore);
        }
      }
    }
    this.processed.clear("updateDocument");
    return this;
  }
  documentStyleSheet() {
    return this.outputJax.styleSheet(this);
  }
  documentPageElements() {
    return this.outputJax.pageElements(this);
  }
  addStyles(styles) {
    this.styles.push(styles);
    if ("insertStyles" in this.outputJax) {
      this.outputJax.insertStyles(styles);
    }
  }
  getStyles() {
    return this.styles;
  }
};
HTMLDocument.KIND = "HTML";
HTMLDocument.OPTIONS = Object.assign(Object.assign({}, AbstractMathDocument.OPTIONS), { renderActions: expandable(Object.assign(Object.assign({}, AbstractMathDocument.OPTIONS.renderActions), { styles: [STATE.STYLES, "", "updateStyleSheet", false] })), MathList: HTMLMathList, MathItem: HTMLMathItem, DomStrings: null });

// node_modules/@mathjax/src/mjs/handlers/html/HTMLHandler.js
var HTMLHandler = class extends AbstractHandler {
  constructor() {
    super(...arguments);
    this.documentClass = HTMLDocument;
  }
  handlesDocument(document2) {
    const adaptor2 = this.adaptor;
    if (typeof document2 === "string") {
      try {
        document2 = adaptor2.parse(document2, "text/html");
      } catch (_err) {
      }
    }
    if (document2 instanceof adaptor2.window.Document || document2 instanceof adaptor2.window.HTMLElement || document2 instanceof adaptor2.window.DocumentFragment) {
      return true;
    }
    return false;
  }
  create(document2, options2) {
    const adaptor2 = this.adaptor;
    if (typeof document2 === "string") {
      document2 = adaptor2.parse(document2, "text/html");
    } else if (document2 instanceof adaptor2.window.HTMLElement || document2 instanceof adaptor2.window.DocumentFragment) {
      const child = document2;
      document2 = adaptor2.parse("", "text/html");
      adaptor2.append(adaptor2.body(document2), child);
    }
    return super.create(document2, options2);
  }
};

// node_modules/@mathjax/src/mjs/handlers/html.js
function RegisterHTMLHandler(adaptor2) {
  const handler = new HTMLHandler(adaptor2);
  mathjax.handlers.register(handler);
  return handler;
}

// node_modules/@mathjax/src/mjs/core/Tree/Visitor.js
var AbstractVisitor = class _AbstractVisitor {
  static methodName(kind) {
    return "visit" + (kind.charAt(0).toUpperCase() + kind.substring(1)).replace(/[^a-z0-9_]/gi, "_") + "Node";
  }
  constructor(factory) {
    this.nodeHandlers = /* @__PURE__ */ new Map();
    for (const kind of factory.getKinds()) {
      const method = this[_AbstractVisitor.methodName(kind)];
      if (method) {
        this.nodeHandlers.set(kind, method);
      }
    }
  }
  visitTree(tree, ...args) {
    return this.visitNode(tree, ...args);
  }
  visitNode(node, ...args) {
    const handler = this.nodeHandlers.get(node.kind) || this.visitDefault;
    return handler.call(this, node, ...args);
  }
  visitDefault(node, ...args) {
    if ("childNodes" in node) {
      for (const child of node.childNodes) {
        this.visitNode(child, ...args);
      }
    }
  }
  setNodeHandler(kind, handler) {
    this.nodeHandlers.set(kind, handler);
  }
  removeNodeHandler(kind) {
    this.nodeHandlers.delete(kind);
  }
};

// node_modules/@mathjax/src/mjs/core/MmlTree/MmlVisitor.js
var DATAMJX = "data-mjx-";
var MmlVisitor = class extends AbstractVisitor {
  constructor(factory = null) {
    if (!factory) {
      factory = new MmlFactory();
    }
    super(factory);
  }
  visitTextNode(_node, ..._args) {
  }
  visitXMLNode(_node, ..._args) {
  }
  visitHtmlNode(_node, ..._args) {
  }
  getKind(node) {
    const kind = node.kind;
    return lookup(kind, this.constructor.rename, kind);
  }
  getAttributeList(node) {
    const CLASS = this.constructor;
    const defaults = lookup(node.kind, CLASS.defaultAttributes, {});
    const attributes = Object.assign({}, defaults, this.getDataAttributes(node), node.attributes.getAllAttributes());
    const variants = CLASS.variants;
    if (Object.hasOwn(attributes, "mathvariant")) {
      if (Object.hasOwn(variants, attributes.mathvariant)) {
        attributes.mathvariant = variants[attributes.mathvariant];
      } else if (node.getProperty("ignore-variant")) {
        delete attributes.mathvariant;
      }
    }
    return attributes;
  }
  getDataAttributes(node) {
    const data = {};
    const variant = node.attributes.getExplicit("mathvariant");
    const variants = this.constructor.variants;
    if (variant && (node.getProperty("ignore-variant") || Object.hasOwn(variants, variant))) {
      this.setDataAttribute(data, "variant", variant);
    }
    if (node.getProperty("variantForm")) {
      this.setDataAttribute(data, "alternate", "1");
    }
    if (node.getProperty("pseudoscript")) {
      this.setDataAttribute(data, "pseudoscript", "true");
    }
    if (node.getProperty("autoOP") === false) {
      this.setDataAttribute(data, "auto-op", "false");
    }
    const vbox = node.getProperty("vbox");
    if (vbox) {
      this.setDataAttribute(data, "vbox", vbox);
    }
    const scriptalign = node.getProperty("scriptalign");
    if (scriptalign) {
      this.setDataAttribute(data, "script-align", scriptalign);
    }
    const accent = node.getProperty("mathaccent");
    if (accent !== void 0) {
      if (accent && !node.isMathAccent() || !accent && !node.isMathAccentWithWidth()) {
        this.setDataAttribute(data, "mathaccent", accent.toString());
      }
    }
    const texclass = node.getProperty("texClass");
    if (texclass !== void 0) {
      let setclass = true;
      if (texclass === TEXCLASS.OP && node.isKind("mi")) {
        const name = node.getText();
        setclass = !(name.length > 1 && name.match(MmlMi.operatorName));
      }
      if (setclass) {
        this.setDataAttribute(data, "texclass", texclass < 0 ? "NONE" : TEXCLASSNAMES[texclass]);
      }
    }
    if (node.getProperty("smallmatrix")) {
      this.setDataAttribute(data, "smallmatrix", "true");
    }
    return data;
  }
  setDataAttribute(data, name, value) {
    data[DATAMJX + name] = value;
  }
};
MmlVisitor.rename = {
  TeXAtom: "mrow"
};
MmlVisitor.variants = {
  "-tex-calligraphic": "script",
  "-tex-bold-calligraphic": "bold-script",
  "-tex-oldstyle": "normal",
  "-tex-bold-oldstyle": "bold",
  "-tex-mathit": "italic"
};
MmlVisitor.defaultAttributes = {
  math: {
    xmlns: "http://www.w3.org/1998/Math/MathML"
  }
};

// node_modules/@mathjax/src/mjs/core/MmlTree/SerializedMmlVisitor.js
var SerializedMmlVisitor = class extends MmlVisitor {
  visitTree(node) {
    return this.visitNode(node, "");
  }
  visitTextNode(node, _space) {
    return this.quoteHTML(node.getText());
  }
  visitXMLNode(node, space) {
    return space + node.getSerializedXML();
  }
  visitHtmlNode(node, _space) {
    return node.getSerializedHTML();
  }
  visitInferredMrowNode(node, space) {
    const mml = [];
    for (const child of node.childNodes) {
      mml.push(this.visitNode(child, space));
    }
    return mml.join("\n");
  }
  visitAnnotationNode(node, space) {
    const children = this.childNodeMml(node, "", "");
    return `${space}<annotation${this.getAttributes(node)}>${children}</annotation>`;
  }
  visitDefault(node, space) {
    const kind = this.getKind(node);
    const [nl, endspace] = node.isToken || node.childNodes.length === 0 ? ["", ""] : ["\n", space];
    const children = this.childNodeMml(node, space + "  ", nl);
    const childNode = children.match(/\S/) ? nl + children + endspace : "";
    return `${space}<${kind}${this.getAttributes(node)}>${childNode}</${kind}>`;
  }
  childNodeMml(node, space, nl) {
    let mml = "";
    for (const child of node.childNodes) {
      mml += this.visitNode(child, space) + nl;
    }
    return mml;
  }
  getAttributes(node) {
    const attr = [];
    const attributes = this.getAttributeList(node);
    for (const name of Object.keys(attributes)) {
      const value = String(attributes[name]);
      if (value === void 0)
        continue;
      attr.push(name + '="' + this.quoteHTML(value) + '"');
    }
    return attr.length ? " " + attr.join(" ") : "";
  }
  quoteHTML(value) {
    return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/[\uD800-\uDBFF]./g, this.toEntity).replace(/[\u0080-\uD7FF\uE000-\uFFFF]/g, this.toEntity);
  }
  toEntity(c) {
    return toEntity(c);
  }
};

// node_modules/@mathjax/src/mjs/input/tex/ams/AmsItems.js
var MultlineItem = class extends ArrayItem {
  constructor(factory, ...args) {
    super(factory);
    this.factory.configuration.tags.start("multline", true, args[0]);
  }
  get kind() {
    return "multline";
  }
  EndEntry() {
    if (this.table.length) {
      ParseUtil.fixInitialMO(this.factory.configuration, this.nodes);
    }
    const shove = this.getProperty("shove");
    const mtd = this.create("node", "mtd", this.nodes, shove ? { columnalign: shove } : {});
    this.setProperty("shove", null);
    this.row.push(mtd);
    this.Clear();
  }
  EndRow() {
    if (this.row.length !== 1) {
      throw new TexError_default("MultlineRowsOneCol", "The rows within the %1 environment must have exactly one column", "multline");
    }
    const row = this.create("node", "mtr", this.row);
    this.table.push(row);
    this.row = [];
  }
  EndTable() {
    super.EndTable();
    if (this.table.length) {
      const m = this.table.length - 1;
      let label = -1;
      if (!NodeUtil_default.getAttribute(NodeUtil_default.getChildren(this.table[0])[0], "columnalign")) {
        NodeUtil_default.setAttribute(NodeUtil_default.getChildren(this.table[0])[0], "columnalign", TexConstant.Align.LEFT);
      }
      if (!NodeUtil_default.getAttribute(NodeUtil_default.getChildren(this.table[m])[0], "columnalign")) {
        NodeUtil_default.setAttribute(NodeUtil_default.getChildren(this.table[m])[0], "columnalign", TexConstant.Align.RIGHT);
      }
      const tag = this.factory.configuration.tags.getTag();
      if (tag) {
        label = this.arraydef.side === TexConstant.Align.LEFT ? 0 : this.table.length - 1;
        const mtr = this.table[label];
        const mlabel = this.create("node", "mlabeledtr", [tag].concat(NodeUtil_default.getChildren(mtr)));
        NodeUtil_default.copyAttributes(mtr, mlabel);
        this.table[label] = mlabel;
      }
    }
    this.factory.configuration.tags.end();
  }
};
var FlalignItem = class extends EqnArrayItem {
  get kind() {
    return "flalign";
  }
  constructor(factory, name, numbered, padded, center) {
    super(factory);
    this.name = name;
    this.numbered = numbered;
    this.padded = padded;
    this.center = center;
    this.factory.configuration.tags.start(name, numbered, numbered);
  }
  EndEntry() {
    super.EndEntry();
    const n = this.getProperty("xalignat");
    if (!n)
      return;
    if (this.row.length > n) {
      throw new TexError_default("XalignOverflow", "Extra %1 in row of %2", "&", this.name);
    }
  }
  EndRow() {
    let cell;
    const row = this.row;
    const n = this.getProperty("xalignat");
    while (row.length < n) {
      row.push(this.create("node", "mtd"));
    }
    this.row = [];
    if (this.padded) {
      this.row.push(this.create("node", "mtd"));
    }
    while (cell = row.shift()) {
      this.row.push(cell);
      cell = row.shift();
      if (cell)
        this.row.push(cell);
      if (row.length || this.padded) {
        this.row.push(this.create("node", "mtd"));
      }
    }
    if (this.row.length > this.maxrow) {
      this.maxrow = this.row.length;
    }
    super.EndRow();
    const mtr = this.table[this.table.length - 1];
    if (this.getProperty("zeroWidthLabel") && mtr.isKind("mlabeledtr")) {
      const mtd = NodeUtil_default.getChildren(mtr)[0];
      const side = this.factory.configuration.options["tagSide"];
      const def = Object.assign({ width: 0 }, side === "right" ? { lspace: "-1width" } : {});
      const mpadded = this.create("node", "mpadded", NodeUtil_default.getChildren(mtd), def);
      mtd.setChildren([mpadded]);
    }
  }
  EndTable() {
    super.EndTable();
    if (this.center) {
      if (this.maxrow <= 2) {
        const def = this.arraydef;
        delete def.width;
        delete this.global.indentalign;
      }
    }
  }
};

// node_modules/@mathjax/src/mjs/input/tex/newcommand/NewcommandUtil.js
var NewcommandTables;
(function(NewcommandTables2) {
  NewcommandTables2["NEW_DELIMITER"] = "new-Delimiter";
  NewcommandTables2["NEW_COMMAND"] = "new-Command";
  NewcommandTables2["NEW_ENVIRONMENT"] = "new-Environment";
})(NewcommandTables || (NewcommandTables = {}));
var NewcommandPriority = -100;
var NewcommandUtil = {
  GetCSname(parser, cmd) {
    const c = parser.GetNext();
    if (c !== "\\") {
      throw new TexError_default("MissingCS", "%1 must be followed by a control sequence", cmd);
    }
    const cs = UnitUtil.trimSpaces(parser.GetArgument(cmd)).substring(1);
    this.checkProtectedMacros(parser, cs);
    return cs;
  },
  GetCsNameArgument(parser, name) {
    let cs = UnitUtil.trimSpaces(parser.GetArgument(name));
    if (cs.charAt(0) === "\\") {
      cs = cs.substring(1);
    }
    if (!cs.match(/^(.|[a-z]+)$/i)) {
      throw new TexError_default("IllegalControlSequenceName", "Illegal control sequence name for %1", name);
    }
    this.checkProtectedMacros(parser, cs);
    return cs;
  },
  GetArgCount(parser, name) {
    let n = parser.GetBrackets(name);
    if (n) {
      n = UnitUtil.trimSpaces(n);
      if (!n.match(/^[0-9]+$/)) {
        throw new TexError_default("IllegalParamNumber", "Illegal number of parameters specified in %1", name);
      }
    }
    return n;
  },
  GetTemplate(parser, cmd, cs) {
    let c = parser.GetNext();
    const params = [];
    let n = 0;
    let i = parser.i;
    while (parser.i < parser.string.length) {
      c = parser.GetNext();
      if (c === "#") {
        if (i !== parser.i) {
          params[n] = parser.string.substring(i, parser.i);
        }
        c = parser.string.charAt(++parser.i);
        if (!c.match(/^[1-9]$/)) {
          throw new TexError_default("CantUseHash2", "Illegal use of # in template for %1", cs);
        }
        if (parseInt(c) !== ++n) {
          throw new TexError_default("SequentialParam", "Parameters for %1 must be numbered sequentially", cs);
        }
        i = parser.i + 1;
      } else if (c === "{") {
        if (i !== parser.i) {
          params[n] = parser.string.substring(i, parser.i);
          if (params[n].replace(/^ +/, "") === "" && params.slice(0, n).join("") === "") {
            return n;
          }
        }
        if (params.length > 0) {
          return [n.toString()].concat(params);
        } else {
          return n;
        }
      }
      parser.i++;
    }
    throw new TexError_default("MissingReplacementString", "Missing replacement string for definition of %1", cmd);
  },
  GetParameter(parser, name, param) {
    if (param == null) {
      return parser.GetArgument(name);
    }
    let i = parser.i;
    let j = 0;
    let hasBraces = false;
    while (parser.i < parser.string.length) {
      const c = parser.string.charAt(parser.i);
      if (c === "{") {
        hasBraces = parser.i === i;
        parser.GetArgument(name);
        j = parser.i - i;
      } else if (this.MatchParam(parser, param)) {
        if (hasBraces) {
          i++;
          j -= 2;
        }
        return parser.string.substring(i, i + j);
      } else if (c === "\\") {
        parser.i++;
        j++;
        hasBraces = false;
        const match = parser.string.substring(parser.i).match(/[a-z]+|./i);
        if (match) {
          parser.i += match[0].length;
          j = parser.i - i;
        }
      } else {
        parser.i++;
        j++;
        hasBraces = false;
      }
    }
    throw new TexError_default("RunawayArgument", "Runaway argument for %1?", name);
  },
  MatchParam(parser, param) {
    if (parser.string.substring(parser.i, parser.i + param.length) !== param) {
      return 0;
    }
    if (param.match(/\\[a-z]+$/i) && parser.string.charAt(parser.i + param.length).match(/[a-z]/i)) {
      return 0;
    }
    parser.i += param.length;
    return 1;
  },
  checkGlobal(parser, tokens, maps3) {
    return parser.stack.env.isGlobal ? parser.configuration.packageData.get("begingroup").stack.checkGlobal(tokens, maps3) : maps3.map((name) => parser.configuration.handlers.retrieve(name));
  },
  checkProtectedMacros(parser, cs) {
    var _a;
    if ((_a = parser.options.protectedMacros) === null || _a === void 0 ? void 0 : _a.includes(cs)) {
      throw new TexError_default("ProtectedMacro", "The control sequence %1 can't be redefined", `\\${cs}`);
    }
  },
  addDelimiter(parser, cs, char, attr) {
    const name = cs.substring(1);
    this.checkProtectedMacros(parser, name);
    const [macros, delims] = NewcommandUtil.checkGlobal(parser, [name, cs], [NewcommandTables.NEW_COMMAND, NewcommandTables.NEW_DELIMITER]);
    if (name !== cs) {
      macros.remove(name);
    }
    delims.add(cs, new Token(cs, char, attr));
    delete parser.stack.env.isGlobal;
  },
  addMacro(parser, cs, func, attr, token = "") {
    this.checkProtectedMacros(parser, cs);
    const macros = NewcommandUtil.checkGlobal(parser, [cs], [NewcommandTables.NEW_COMMAND])[0];
    this.undefineDelimiter(parser, "\\" + cs);
    macros.add(cs, new Macro(token ? token : cs, func, attr));
    delete parser.stack.env.isGlobal;
  },
  addEnvironment(parser, env, func, attr) {
    const envs = NewcommandUtil.checkGlobal(parser, [env], [NewcommandTables.NEW_ENVIRONMENT])[0];
    envs.add(env, new Macro(env, func, attr));
    delete parser.stack.env.isGlobal;
  },
  undefineMacro(parser, cs) {
    const macros = NewcommandUtil.checkGlobal(parser, [cs], [NewcommandTables.NEW_COMMAND])[0];
    macros.remove(cs);
    if (parser.configuration.handlers.get(HandlerType.MACRO).applicable(cs)) {
      macros.add(cs, new Macro(cs, () => SubHandler.FALLBACK, []));
      this.undefineDelimiter(parser, "\\" + cs);
    }
    delete parser.stack.env.isGlobal;
  },
  undefineDelimiter(parser, cs) {
    const delims = NewcommandUtil.checkGlobal(parser, [cs], [NewcommandTables.NEW_DELIMITER])[0];
    delims.remove(cs);
    if (parser.configuration.handlers.get(HandlerType.DELIMITER).applicable(cs)) {
      delims.add(cs, new Token(cs, null, {}));
    }
    delete parser.stack.env.isGlobal;
  }
};

// node_modules/@mathjax/src/mjs/input/tex/ams/AmsMethods.js
function splitSideSet(mml) {
  if (!mml || mml.isInferred && mml.childNodes.length === 0) {
    return [null, null];
  }
  if (mml.isKind("msubsup") && checkSideSetBase(mml)) {
    return [mml, null];
  }
  const child = NodeUtil_default.getChildAt(mml, 0);
  if (!(mml.isInferred && child && checkSideSetBase(child))) {
    return [null, mml];
  }
  mml.childNodes.splice(0, 1);
  return [child, mml];
}
function checkSideSetBase(mml) {
  const base = mml.childNodes[0];
  return base && base.isKind("mi") && base.getText() === "";
}
var AmsMethods = {
  AmsEqnArray(parser, begin, numbered, taggable, align, balign, spacing, style) {
    const args = parser.GetBrackets("\\begin{" + begin.getName() + "}");
    const array = BaseMethods_default.EqnArray(parser, begin, numbered, taggable, align, balign, spacing, style);
    return ParseUtil.setArrayAlign(array, args, parser);
  },
  AlignAt(parser, begin, numbered, taggable) {
    const name = begin.getName();
    let valign;
    let align = "";
    let balign = "";
    const spacing = [];
    if (!taggable) {
      valign = parser.GetBrackets("\\begin{" + name + "}");
    }
    const n = parser.GetArgument("\\begin{" + name + "}");
    if (n.match(/[^0-9]/)) {
      throw new TexError_default("PositiveIntegerArg", "Argument to %1 must be a positive integer", "\\begin{" + name + "}");
    }
    let count = parseInt(n, 10);
    while (count > 0) {
      align += "rl";
      balign += "bt";
      spacing.push("0em 0em");
      count--;
    }
    const spaceStr = spacing.join(" ");
    if (taggable) {
      return AmsMethods.EqnArray(parser, begin, numbered, taggable, align, balign, spaceStr);
    }
    const array = AmsMethods.EqnArray(parser, begin, numbered, taggable, align, balign, spaceStr);
    return ParseUtil.setArrayAlign(array, valign, parser);
  },
  Multline(parser, begin, numbered) {
    ParseUtil.checkEqnEnv(parser);
    parser.Push(begin);
    const padding = parser.options.ams["multlineIndent"];
    const item = parser.itemFactory.create("multline", numbered, parser.stack);
    item.arraydef = {
      displaystyle: true,
      rowspacing: ".5em",
      columnspacing: "100%",
      width: parser.options.ams["multlineWidth"],
      side: parser.options["tagSide"],
      minlabelspacing: parser.options["tagIndent"],
      "data-array-padding": `${padding} ${padding}`,
      "data-width-includes-label": true
    };
    return item;
  },
  XalignAt(parser, begin, numbered, padded) {
    const n = parser.GetArgument("\\begin{" + begin.getName() + "}");
    if (n.match(/[^0-9]/)) {
      throw new TexError_default("PositiveIntegerArg", "Argument to %1 must be a positive integer", "\\begin{" + begin.getName() + "}");
    }
    const align = padded ? "crl" : "rlc";
    const balign = padded ? "mbt" : "btm";
    const width = padded ? "fit auto auto" : "auto auto fit";
    const item = AmsMethods.FlalignArray(parser, begin, numbered, padded, false, align, balign, width, true);
    item.setProperty("xalignat", 2 * parseInt(n));
    return item;
  },
  FlalignArray(parser, begin, numbered, padded, center, align, balign, width, zeroWidthLabel = false) {
    ParseUtil.checkEqnEnv(parser);
    parser.Push(begin);
    align = align.split("").join(" ").replace(/r/g, "right").replace(/l/g, "left").replace(/c/g, "center");
    balign = splitAlignArray(balign);
    const item = parser.itemFactory.create("flalign", begin.getName(), numbered, padded, center, parser.stack);
    item.arraydef = {
      width: "100%",
      displaystyle: true,
      columnalign: align,
      columnspacing: "0em",
      columnwidth: width,
      rowspacing: "3pt",
      "data-break-align": balign,
      side: parser.options["tagSide"],
      minlabelspacing: zeroWidthLabel ? "0" : parser.options["tagIndent"],
      "data-width-includes-label": true
    };
    item.setProperty("zeroWidthLabel", zeroWidthLabel);
    return item;
  },
  HandleDeclareOp(parser, name) {
    const star = parser.GetStar() ? "*" : "";
    const cs = NewcommandUtil.GetCsNameArgument(parser, name);
    const op = parser.GetArgument(name);
    NewcommandUtil.addMacro(parser, cs, AmsMethods.Macro, [
      `\\operatorname${star}{${op}}`
    ]);
    parser.Push(parser.itemFactory.create("null"));
  },
  HandleOperatorName(parser, name) {
    const star = parser.GetStar();
    const op = UnitUtil.trimSpaces(parser.GetArgument(name));
    let mml = new TexParser(op, Object.assign(Object.assign({}, parser.stack.env), { font: TexConstant.Variant.NORMAL, multiLetterIdentifiers: parser.options.ams.operatornamePattern, operatorLetters: true, noAutoOP: true }), parser.configuration).mml();
    if (mml.isKind("mi")) {
      mml.removeProperty("autoOP");
    } else {
      mml = parser.create("node", "TeXAtom", [mml]);
    }
    NodeUtil_default.setProperties(mml, {
      movesupsub: star,
      movablelimits: true,
      texClass: TEXCLASS.OP
    });
    if (!star) {
      const c = parser.GetNext();
      const i = parser.i;
      if (c === "\\" && ++parser.i && parser.GetCS() !== "limits") {
        parser.i = i;
      }
    }
    parser.Push(parser.itemFactory.create("fn", mml));
  },
  SideSet(parser, name) {
    const [preScripts, preRest] = splitSideSet(parser.ParseArg(name));
    const [postScripts, postRest] = splitSideSet(parser.ParseArg(name));
    const base = parser.ParseArg(name);
    let mml = base;
    if (preScripts) {
      if (preRest) {
        preScripts.replaceChild(parser.create("node", "mphantom", [
          parser.create("node", "mpadded", [ParseUtil.copyNode(base, parser)], { width: 0 })
        ]), NodeUtil_default.getChildAt(preScripts, 0));
      } else {
        mml = parser.create("node", "mmultiscripts", [base]);
        if (postScripts) {
          NodeUtil_default.appendChildren(mml, [
            NodeUtil_default.getChildAt(postScripts, 1) || parser.create("node", "none"),
            NodeUtil_default.getChildAt(postScripts, 2) || parser.create("node", "none")
          ]);
        }
        NodeUtil_default.setProperty(mml, "scriptalign", "left");
        NodeUtil_default.appendChildren(mml, [
          parser.create("node", "mprescripts"),
          NodeUtil_default.getChildAt(preScripts, 1) || parser.create("node", "none"),
          NodeUtil_default.getChildAt(preScripts, 2) || parser.create("node", "none")
        ]);
      }
    }
    if (postScripts && mml === base) {
      postScripts.replaceChild(base, NodeUtil_default.getChildAt(postScripts, 0));
      mml = postScripts;
    }
    const mrow = parser.create("node", "TeXAtom", [], {
      texClass: TEXCLASS.OP,
      movesupsub: true,
      movablelimits: true
    });
    if (preRest) {
      if (preScripts) {
        mrow.appendChild(preScripts);
      }
      mrow.appendChild(preRest);
    }
    mrow.appendChild(mml);
    if (postRest) {
      mrow.appendChild(postRest);
    }
    parser.Push(mrow);
  },
  operatorLetter(parser, c) {
    return parser.stack.env.operatorLetters ? ParseMethods_default.variable(parser, c) : false;
  },
  MultiIntegral(parser, name, integral) {
    let next = parser.GetNext();
    if (next === "\\") {
      const i = parser.i;
      next = parser.GetArgument(name);
      parser.i = i;
      if (next === "\\limits") {
        integral = "\\!\\!\\mathop{\\,\\," + integral + "}";
      }
    }
    parser.string = integral + " " + parser.string.slice(parser.i);
    parser.i = 0;
  },
  xArrow(parser, name, chr, l, r, m = 0) {
    const def = {
      width: "+" + UnitUtil.em((l + r) / 18),
      lspace: UnitUtil.em(l / 18)
    };
    const bot = parser.GetBrackets(name);
    const first = parser.ParseArg(name);
    const dstrut = parser.create("node", "mspace", [], { depth: ".2em" });
    let arrow = parser.create("token", "mo", { stretchy: true, texClass: TEXCLASS.ORD }, String.fromCodePoint(chr));
    if (m) {
      arrow.attributes.set("minsize", UnitUtil.em(m));
    }
    arrow = parser.create("node", "mstyle", [arrow], { scriptlevel: 0 });
    const mml = parser.create("node", "munderover", [arrow]);
    let mpadded = parser.create("node", "mpadded", [first, dstrut], def);
    NodeUtil_default.setAttribute(mpadded, "voffset", "-.2em");
    NodeUtil_default.setAttribute(mpadded, "height", "-.2em");
    NodeUtil_default.setChild(mml, mml.over, mpadded);
    if (bot) {
      const bottom = new TexParser(bot, parser.stack.env, parser.configuration).mml();
      const bstrut = parser.create("node", "mspace", [], { height: ".75em" });
      mpadded = parser.create("node", "mpadded", [bottom, bstrut], def);
      NodeUtil_default.setAttribute(mpadded, "voffset", ".15em");
      NodeUtil_default.setAttribute(mpadded, "depth", "-.15em");
      NodeUtil_default.setChild(mml, mml.under, mpadded);
    }
    NodeUtil_default.setProperty(mml, "subsupOK", true);
    parser.Push(parser.create("node", "TeXAtom", [
      parser.create("node", "TeXAtom", [], {
        texClass: TEXCLASS.NONE
      }),
      mml
    ], { texClass: TEXCLASS.REL }));
  },
  HandleShove(parser, _name, shove) {
    const top = parser.stack.Top();
    if (top.kind !== "multline") {
      throw new TexError_default("CommandOnlyAllowedInEnv", "%1 only allowed in %2 environment", parser.currentCS, "multline");
    }
    if (top.Size()) {
      throw new TexError_default("CommandAtTheBeginingOfLine", "%1 must come at the beginning of the line", parser.currentCS);
    }
    top.setProperty("shove", shove);
  },
  CFrac(parser, name) {
    let lr = UnitUtil.trimSpaces(parser.GetBrackets(name, ""));
    const num = parser.GetArgument(name);
    const den = parser.GetArgument(name);
    const lrMap = {
      l: TexConstant.Align.LEFT,
      r: TexConstant.Align.RIGHT,
      "": ""
    };
    const numNode = new TexParser("\\strut\\textstyle{" + num + "}", parser.stack.env, parser.configuration).mml();
    const denNode = new TexParser("\\strut\\textstyle{" + den + "}", parser.stack.env, parser.configuration).mml();
    const frac = parser.create("node", "mfrac", [numNode, denNode]);
    lr = lrMap[lr];
    if (lr == null) {
      throw new TexError_default("IllegalAlign", "Illegal alignment specified in %1", parser.currentCS);
    }
    if (lr) {
      NodeUtil_default.setProperties(frac, { numalign: lr, denomalign: lr });
    }
    parser.Push(frac);
  },
  Genfrac(parser, name, left, right, thick, style) {
    if (left == null) {
      left = parser.GetDelimiterArg(name);
    }
    if (right == null) {
      right = parser.GetDelimiterArg(name);
    }
    if (thick == null) {
      thick = parser.GetArgument(name);
    }
    if (style == null) {
      style = UnitUtil.trimSpaces(parser.GetArgument(name));
    }
    const num = parser.ParseArg(name);
    const den = parser.ParseArg(name);
    let frac = parser.create("node", "mfrac", [num, den]);
    if (thick !== "") {
      NodeUtil_default.setAttribute(frac, "linethickness", thick);
    }
    if (left || right) {
      NodeUtil_default.setProperty(frac, "withDelims", true);
      frac = ParseUtil.fixedFence(parser.configuration, left, frac, right);
    }
    if (style !== "") {
      const styleDigit = parseInt(style, 10);
      const styleAlpha = ["D", "T", "S", "SS"][styleDigit];
      if (styleAlpha == null) {
        throw new TexError_default("BadMathStyleFor", "Bad math style for %1", parser.currentCS);
      }
      frac = parser.create("node", "mstyle", [frac]);
      if (styleAlpha === "D") {
        NodeUtil_default.setProperties(frac, { displaystyle: true, scriptlevel: 0 });
      } else {
        NodeUtil_default.setProperties(frac, {
          displaystyle: false,
          scriptlevel: styleDigit - 1
        });
      }
    }
    parser.Push(frac);
  },
  HandleTag(parser, name) {
    if (!parser.tags.currentTag.taggable && parser.tags.env) {
      throw new TexError_default("CommandNotAllowedInEnv", "%1 not allowed in %2 environment", parser.currentCS, parser.tags.env);
    }
    if (parser.tags.currentTag.tag) {
      throw new TexError_default("MultipleCommand", "Multiple %1", parser.currentCS);
    }
    const star = parser.GetStar();
    const tagId = UnitUtil.trimSpaces(parser.GetArgument(name));
    parser.tags.tag(tagId, star);
    parser.Push(parser.itemFactory.create("null"));
  },
  HandleNoTag: BaseMethods_default.HandleNoTag,
  HandleRef: BaseMethods_default.HandleRef,
  Macro: BaseMethods_default.Macro,
  Accent: BaseMethods_default.Accent,
  Tilde: BaseMethods_default.Tilde,
  Array: BaseMethods_default.Array,
  Spacer: BaseMethods_default.Spacer,
  NamedOp: BaseMethods_default.NamedOp,
  EqnArray: BaseMethods_default.EqnArray,
  Equation: BaseMethods_default.Equation
};

// node_modules/@mathjax/src/mjs/input/tex/ams/AmsMappings.js
new CharacterMap("AMSmath-mathchar0mo", ParseMethods_default.mathchar0mo, {
  iiiint: ["\u2A0C", { texClass: TEXCLASS.OP }]
});
new RegExpMap("AMSmath-operatorLetter", AmsMethods.operatorLetter, /[-*]/i);
new CommandMap("AMSmath-macros", {
  mathring: [AmsMethods.Accent, "02DA"],
  nobreakspace: AmsMethods.Tilde,
  negmedspace: [AmsMethods.Spacer, MATHSPACE.negativemediummathspace],
  negthickspace: [AmsMethods.Spacer, MATHSPACE.negativethickmathspace],
  idotsint: [AmsMethods.MultiIntegral, "\\int\\cdots\\int"],
  dddot: [AmsMethods.Accent, "20DB"],
  ddddot: [AmsMethods.Accent, "20DC"],
  sideset: AmsMethods.SideSet,
  boxed: [AmsMethods.Macro, "\\fbox{$\\displaystyle{#1}$}", 1],
  tag: AmsMethods.HandleTag,
  notag: AmsMethods.HandleNoTag,
  eqref: [AmsMethods.HandleRef, true],
  substack: [AmsMethods.Macro, "\\begin{subarray}{c}#1\\end{subarray}", 1],
  injlim: [AmsMethods.NamedOp, "inj&thinsp;lim"],
  projlim: [AmsMethods.NamedOp, "proj&thinsp;lim"],
  varliminf: [AmsMethods.Macro, "\\mathop{\\underline{\\mmlToken{mi}{lim}}}"],
  varlimsup: [AmsMethods.Macro, "\\mathop{\\overline{\\mmlToken{mi}{lim}}}"],
  varinjlim: [
    AmsMethods.Macro,
    "\\mathop{\\underrightarrow{\\mmlToken{mi}{lim}}}"
  ],
  varprojlim: [
    AmsMethods.Macro,
    "\\mathop{\\underleftarrow{\\mmlToken{mi}{lim}}}"
  ],
  DeclareMathOperator: AmsMethods.HandleDeclareOp,
  operatorname: AmsMethods.HandleOperatorName,
  genfrac: AmsMethods.Genfrac,
  frac: [AmsMethods.Genfrac, "", "", "", ""],
  tfrac: [AmsMethods.Genfrac, "", "", "", "1"],
  dfrac: [AmsMethods.Genfrac, "", "", "", "0"],
  binom: [AmsMethods.Genfrac, "(", ")", "0", ""],
  tbinom: [AmsMethods.Genfrac, "(", ")", "0", "1"],
  dbinom: [AmsMethods.Genfrac, "(", ")", "0", "0"],
  cfrac: AmsMethods.CFrac,
  shoveleft: [AmsMethods.HandleShove, TexConstant.Align.LEFT],
  shoveright: [AmsMethods.HandleShove, TexConstant.Align.RIGHT],
  xrightarrow: [AmsMethods.xArrow, 8594, 5, 10],
  xleftarrow: [AmsMethods.xArrow, 8592, 10, 5]
});
new EnvironmentMap("AMSmath-environment", ParseMethods_default.environment, {
  "equation*": [AmsMethods.Equation, null, false],
  "eqnarray*": [
    AmsMethods.EqnArray,
    null,
    false,
    true,
    "rcl",
    "bmt",
    ParseUtil.cols(0, MATHSPACE.thickmathspace),
    ".5em"
  ],
  align: [
    AmsMethods.EqnArray,
    null,
    true,
    true,
    "rl",
    "bt",
    ParseUtil.cols(0, 2)
  ],
  "align*": [
    AmsMethods.EqnArray,
    null,
    false,
    true,
    "rl",
    "bt",
    ParseUtil.cols(0, 2)
  ],
  multline: [AmsMethods.Multline, null, true],
  "multline*": [AmsMethods.Multline, null, false],
  split: [
    AmsMethods.EqnArray,
    null,
    false,
    false,
    "rl",
    "bt",
    ParseUtil.cols(0)
  ],
  gather: [AmsMethods.EqnArray, null, true, true, "c", "m"],
  "gather*": [AmsMethods.EqnArray, null, false, true, "c", "m"],
  alignat: [AmsMethods.AlignAt, null, true, true],
  "alignat*": [AmsMethods.AlignAt, null, false, true],
  alignedat: [AmsMethods.AlignAt, null, false, false],
  aligned: [
    AmsMethods.AmsEqnArray,
    null,
    null,
    null,
    "rl",
    "bt",
    ParseUtil.cols(0, 2),
    ".5em",
    "D"
  ],
  gathered: [
    AmsMethods.AmsEqnArray,
    null,
    null,
    null,
    "c",
    "m",
    null,
    ".5em",
    "D"
  ],
  xalignat: [AmsMethods.XalignAt, null, true, true],
  "xalignat*": [AmsMethods.XalignAt, null, false, true],
  xxalignat: [AmsMethods.XalignAt, null, false, false],
  flalign: [
    AmsMethods.FlalignArray,
    null,
    true,
    false,
    true,
    "rlc",
    "btm",
    "auto auto fit"
  ],
  "flalign*": [
    AmsMethods.FlalignArray,
    null,
    false,
    false,
    true,
    "rlc",
    "btm",
    "auto auto fit"
  ],
  subarray: [
    AmsMethods.Array,
    null,
    null,
    null,
    null,
    ParseUtil.cols(0),
    "0.1em",
    "S",
    true
  ],
  smallmatrix: [
    AmsMethods.Array,
    null,
    null,
    null,
    "c",
    ParseUtil.cols(1 / 3),
    ".2em",
    "S",
    true
  ],
  matrix: [AmsMethods.Array, null, null, null, "c"],
  pmatrix: [AmsMethods.Array, null, "(", ")", "c"],
  bmatrix: [AmsMethods.Array, null, "[", "]", "c"],
  Bmatrix: [AmsMethods.Array, null, "\\{", "\\}", "c"],
  vmatrix: [AmsMethods.Array, null, "\\vert", "\\vert", "c"],
  Vmatrix: [AmsMethods.Array, null, "\\Vert", "\\Vert", "c"],
  cases: [AmsMethods.Array, null, "\\{", ".", "ll", null, ".2em", "T"]
});
new DelimiterMap("AMSmath-delimiter", ParseMethods_default.delimiter, {
  "\\lvert": ["|", { texClass: TEXCLASS.OPEN }],
  "\\rvert": ["|", { texClass: TEXCLASS.CLOSE }],
  "\\lVert": ["\u2016", { texClass: TEXCLASS.OPEN }],
  "\\rVert": ["\u2016", { texClass: TEXCLASS.CLOSE }]
});
new CharacterMap("AMSsymbols-mathchar0mi", ParseMethods_default.mathchar0mi, {
  digamma: "\u03DD",
  varkappa: "\u03F0",
  varGamma: ["\u0393", { mathvariant: TexConstant.Variant.ITALIC }],
  varDelta: ["\u0394", { mathvariant: TexConstant.Variant.ITALIC }],
  varTheta: ["\u0398", { mathvariant: TexConstant.Variant.ITALIC }],
  varLambda: ["\u039B", { mathvariant: TexConstant.Variant.ITALIC }],
  varXi: ["\u039E", { mathvariant: TexConstant.Variant.ITALIC }],
  varPi: ["\u03A0", { mathvariant: TexConstant.Variant.ITALIC }],
  varSigma: ["\u03A3", { mathvariant: TexConstant.Variant.ITALIC }],
  varUpsilon: ["\u03A5", { mathvariant: TexConstant.Variant.ITALIC }],
  varPhi: ["\u03A6", { mathvariant: TexConstant.Variant.ITALIC }],
  varPsi: ["\u03A8", { mathvariant: TexConstant.Variant.ITALIC }],
  varOmega: ["\u03A9", { mathvariant: TexConstant.Variant.ITALIC }],
  beth: "\u2136",
  gimel: "\u2137",
  daleth: "\u2138",
  backprime: ["\u2035", { variantForm: true }],
  hslash: "\u210F",
  varnothing: ["\u2205", { variantForm: true }],
  blacktriangle: "\u25B4",
  triangledown: ["\u25BD", { variantForm: true }],
  blacktriangledown: "\u25BE",
  square: "\u25FB",
  Box: "\u25FB",
  blacksquare: "\u25FC",
  lozenge: "\u25CA",
  Diamond: "\u25CA",
  blacklozenge: "\u29EB",
  circledS: ["\u24C8", { mathvariant: TexConstant.Variant.NORMAL }],
  bigstar: "\u2605",
  sphericalangle: "\u2222",
  measuredangle: "\u2221",
  nexists: "\u2204",
  complement: "\u2201",
  mho: "\u2127",
  eth: ["\xF0", { mathvariant: TexConstant.Variant.NORMAL }],
  Finv: "\u2132",
  diagup: "\u2571",
  Game: "\u2141",
  diagdown: "\u2572",
  Bbbk: ["k", { mathvariant: TexConstant.Variant.DOUBLESTRUCK }],
  yen: "\xA5",
  circledR: "\xAE",
  checkmark: "\u2713",
  maltese: "\u2720"
});
new CharacterMap("AMSsymbols-mathchar0mo", ParseMethods_default.mathchar0mo, {
  dotplus: "\u2214",
  ltimes: "\u22C9",
  smallsetminus: ["\u2216", { variantForm: true }],
  rtimes: "\u22CA",
  Cap: "\u22D2",
  doublecap: "\u22D2",
  leftthreetimes: "\u22CB",
  Cup: "\u22D3",
  doublecup: "\u22D3",
  rightthreetimes: "\u22CC",
  barwedge: "\u22BC",
  curlywedge: "\u22CF",
  veebar: "\u22BB",
  curlyvee: "\u22CE",
  doublebarwedge: "\u2A5E",
  boxminus: "\u229F",
  circleddash: "\u229D",
  boxtimes: "\u22A0",
  circledast: "\u229B",
  boxdot: "\u22A1",
  circledcirc: "\u229A",
  boxplus: "\u229E",
  centerdot: ["\u22C5", { variantForm: true }],
  divideontimes: "\u22C7",
  intercal: "\u22BA",
  leqq: "\u2266",
  geqq: "\u2267",
  leqslant: "\u2A7D",
  geqslant: "\u2A7E",
  eqslantless: "\u2A95",
  eqslantgtr: "\u2A96",
  lesssim: "\u2272",
  gtrsim: "\u2273",
  lessapprox: "\u2A85",
  gtrapprox: "\u2A86",
  approxeq: "\u224A",
  lessdot: "\u22D6",
  gtrdot: "\u22D7",
  lll: "\u22D8",
  llless: "\u22D8",
  ggg: "\u22D9",
  gggtr: "\u22D9",
  lessgtr: "\u2276",
  gtrless: "\u2277",
  lesseqgtr: "\u22DA",
  gtreqless: "\u22DB",
  lesseqqgtr: "\u2A8B",
  gtreqqless: "\u2A8C",
  doteqdot: "\u2251",
  Doteq: "\u2251",
  eqcirc: "\u2256",
  risingdotseq: "\u2253",
  circeq: "\u2257",
  fallingdotseq: "\u2252",
  triangleq: "\u225C",
  backsim: "\u223D",
  thicksim: ["\u223C", { variantForm: true }],
  backsimeq: "\u22CD",
  thickapprox: ["\u2248", { variantForm: true }],
  subseteqq: "\u2AC5",
  supseteqq: "\u2AC6",
  Subset: "\u22D0",
  Supset: "\u22D1",
  sqsubset: "\u228F",
  sqsupset: "\u2290",
  preccurlyeq: "\u227C",
  succcurlyeq: "\u227D",
  curlyeqprec: "\u22DE",
  curlyeqsucc: "\u22DF",
  precsim: "\u227E",
  succsim: "\u227F",
  precapprox: "\u2AB7",
  succapprox: "\u2AB8",
  vartriangleleft: "\u22B2",
  lhd: "\u22B2",
  vartriangleright: "\u22B3",
  rhd: "\u22B3",
  trianglelefteq: "\u22B4",
  unlhd: "\u22B4",
  trianglerighteq: "\u22B5",
  unrhd: "\u22B5",
  vDash: "\u22A8",
  Vdash: "\u22A9",
  Vvdash: "\u22AA",
  smallsmile: ["\u2323", { variantForm: true }],
  shortmid: ["\u2223", { variantForm: true }],
  smallfrown: ["\u2322", { variantForm: true }],
  shortparallel: ["\u2225", { variantForm: true }],
  bumpeq: "\u224F",
  between: "\u226C",
  Bumpeq: "\u224E",
  pitchfork: "\u22D4",
  varpropto: ["\u221D", { variantForm: true }],
  backepsilon: "\u220D",
  blacktriangleleft: "\u25C2",
  blacktriangleright: "\u25B8",
  therefore: "\u2234",
  because: "\u2235",
  eqsim: "\u2242",
  vartriangle: ["\u25B3", { variantForm: true }],
  Join: "\u22C8",
  nless: "\u226E",
  ngtr: "\u226F",
  nleq: "\u2270",
  ngeq: "\u2271",
  nleqslant: ["\u2A87", { variantForm: true }],
  ngeqslant: ["\u2A88", { variantForm: true }],
  nleqq: ["\u2270", { variantForm: true }],
  ngeqq: ["\u2271", { variantForm: true }],
  lneq: "\u2A87",
  gneq: "\u2A88",
  lneqq: "\u2268",
  gneqq: "\u2269",
  lvertneqq: ["\u2268", { variantForm: true }],
  gvertneqq: ["\u2269", { variantForm: true }],
  lnsim: "\u22E6",
  gnsim: "\u22E7",
  lnapprox: "\u2A89",
  gnapprox: "\u2A8A",
  nprec: "\u2280",
  nsucc: "\u2281",
  npreceq: ["\u22E0", { variantForm: true }],
  nsucceq: ["\u22E1", { variantForm: true }],
  precneqq: "\u2AB5",
  succneqq: "\u2AB6",
  precnsim: "\u22E8",
  succnsim: "\u22E9",
  precnapprox: "\u2AB9",
  succnapprox: "\u2ABA",
  nsim: "\u2241",
  ncong: "\u2247",
  nshortmid: ["\u2224", { variantForm: true }],
  nshortparallel: ["\u2226", { variantForm: true }],
  nmid: "\u2224",
  nparallel: "\u2226",
  nvdash: "\u22AC",
  nvDash: "\u22AD",
  nVdash: "\u22AE",
  nVDash: "\u22AF",
  ntriangleleft: "\u22EA",
  ntriangleright: "\u22EB",
  ntrianglelefteq: "\u22EC",
  ntrianglerighteq: "\u22ED",
  nsubseteq: "\u2288",
  nsupseteq: "\u2289",
  nsubseteqq: ["\u2288", { variantForm: true }],
  nsupseteqq: ["\u2289", { variantForm: true }],
  subsetneq: "\u228A",
  supsetneq: "\u228B",
  varsubsetneq: ["\u228A", { variantForm: true }],
  varsupsetneq: ["\u228B", { variantForm: true }],
  subsetneqq: "\u2ACB",
  supsetneqq: "\u2ACC",
  varsubsetneqq: ["\u2ACB", { variantForm: true }],
  varsupsetneqq: ["\u2ACC", { variantForm: true }],
  leftleftarrows: "\u21C7",
  rightrightarrows: "\u21C9",
  leftrightarrows: "\u21C6",
  rightleftarrows: "\u21C4",
  Lleftarrow: "\u21DA",
  Rrightarrow: "\u21DB",
  twoheadleftarrow: "\u219E",
  twoheadrightarrow: "\u21A0",
  leftarrowtail: "\u21A2",
  rightarrowtail: "\u21A3",
  looparrowleft: "\u21AB",
  looparrowright: "\u21AC",
  leftrightharpoons: "\u21CB",
  rightleftharpoons: ["\u21CC", { variantForm: true }],
  curvearrowleft: "\u21B6",
  curvearrowright: "\u21B7",
  circlearrowleft: "\u21BA",
  circlearrowright: "\u21BB",
  Lsh: "\u21B0",
  Rsh: "\u21B1",
  upuparrows: "\u21C8",
  downdownarrows: "\u21CA",
  upharpoonleft: "\u21BF",
  upharpoonright: "\u21BE",
  downharpoonleft: "\u21C3",
  restriction: "\u21BE",
  multimap: "\u22B8",
  downharpoonright: "\u21C2",
  leftrightsquigarrow: "\u21AD",
  rightsquigarrow: "\u21DD",
  leadsto: "\u21DD",
  dashrightarrow: "\u21E2",
  dashleftarrow: "\u21E0",
  nleftarrow: "\u219A",
  nrightarrow: "\u219B",
  nLeftarrow: "\u21CD",
  nRightarrow: "\u21CF",
  nleftrightarrow: "\u21AE",
  nLeftrightarrow: "\u21CE"
});
new DelimiterMap("AMSsymbols-delimiter", ParseMethods_default.delimiter, {
  "\\ulcorner": "\u231C",
  "\\urcorner": "\u231D",
  "\\llcorner": "\u231E",
  "\\lrcorner": "\u231F"
});
new CommandMap("AMSsymbols-macros", {
  implies: [AmsMethods.Macro, "\\;\\Longrightarrow\\;"],
  impliedby: [AmsMethods.Macro, "\\;\\Longleftarrow\\;"]
});

// node_modules/@mathjax/src/mjs/input/tex/newcommand/NewcommandItems.js
var BeginEnvItem = class extends BaseItem {
  get kind() {
    return "beginEnv";
  }
  get isOpen() {
    return true;
  }
  checkItem(item) {
    if (item.isKind("end")) {
      if (item.getName() !== this.getName()) {
        throw new TexError_default("EnvBadEnd", "\\begin{%1} ended with \\end{%2}", this.getName(), item.getName());
      }
      return [[this.factory.create("mml", this.toMml())], true];
    }
    if (item.isKind("stop")) {
      throw new TexError_default("EnvMissingEnd", "Missing \\end{%1}", this.getName());
    }
    return super.checkItem(item);
  }
};

// node_modules/@mathjax/src/mjs/input/tex/newcommand/NewcommandMethods.js
var NewcommandMethods = {
  NewCommand(parser, name) {
    const cs = NewcommandUtil.GetCsNameArgument(parser, name);
    const n = NewcommandUtil.GetArgCount(parser, name);
    const opt = parser.GetBrackets(name);
    const def = parser.GetArgument(name);
    NewcommandUtil.addMacro(parser, cs, NewcommandMethods.Macro, [def, n, opt]);
    parser.Push(parser.itemFactory.create("null"));
  },
  NewEnvironment(parser, name) {
    const env = UnitUtil.trimSpaces(parser.GetArgument(name));
    const n = NewcommandUtil.GetArgCount(parser, name);
    const opt = parser.GetBrackets(name);
    const bdef = parser.GetArgument(name);
    const edef = parser.GetArgument(name);
    NewcommandUtil.addEnvironment(parser, env, NewcommandMethods.BeginEnv, [
      true,
      bdef,
      edef,
      n,
      opt
    ]);
    parser.Push(parser.itemFactory.create("null"));
  },
  MacroDef(parser, name) {
    const cs = NewcommandUtil.GetCSname(parser, name);
    const params = NewcommandUtil.GetTemplate(parser, name, "\\" + cs);
    const def = parser.GetArgument(name);
    !(params instanceof Array) ? NewcommandUtil.addMacro(parser, cs, NewcommandMethods.Macro, [
      def,
      params
    ]) : NewcommandUtil.addMacro(parser, cs, NewcommandMethods.MacroWithTemplate, [def].concat(params));
    parser.Push(parser.itemFactory.create("null"));
  },
  Let(parser, name) {
    const cs = NewcommandUtil.GetCSname(parser, name);
    let c = parser.GetNext();
    if (c === "=") {
      parser.i++;
      c = parser.GetNext();
    }
    const handlers = parser.configuration.handlers;
    parser.Push(parser.itemFactory.create("null"));
    if (c === "\\") {
      name = NewcommandUtil.GetCSname(parser, name);
      if (cs === name) {
        return;
      }
      const map = handlers.get(HandlerType.MACRO).applicable(name);
      if (map instanceof MacroMap) {
        const macro3 = map.lookup(name);
        NewcommandUtil.addMacro(parser, cs, macro3.func, macro3.args, macro3.token);
        return;
      }
      if (map instanceof CharacterMap && !(map instanceof DelimiterMap)) {
        const macro3 = map.lookup(name);
        const method = (p) => map.parser(p, macro3);
        NewcommandUtil.addMacro(parser, cs, method, [cs, macro3.char]);
        return;
      }
      const macro2 = handlers.get(HandlerType.DELIMITER).lookup("\\" + name);
      if (macro2) {
        NewcommandUtil.addDelimiter(parser, "\\" + cs, macro2.char, macro2.attributes);
        return;
      }
      NewcommandUtil.checkProtectedMacros(parser, cs);
      NewcommandUtil.undefineMacro(parser, cs);
      NewcommandUtil.undefineDelimiter(parser, "\\" + cs);
      return;
    }
    parser.i++;
    const macro = handlers.get(HandlerType.DELIMITER).lookup(c);
    if (macro) {
      NewcommandUtil.addDelimiter(parser, "\\" + cs, macro.char, macro.attributes);
      return;
    }
    NewcommandUtil.addMacro(parser, cs, NewcommandMethods.Macro, [c]);
  },
  MacroWithTemplate(parser, name, text, n, ...params) {
    const argCount = parseInt(n, 10);
    if (params.length) {
      const args = [];
      parser.GetNext();
      if (params[0] && !NewcommandUtil.MatchParam(parser, params[0])) {
        throw new TexError_default("MismatchUseDef", "Use of %1 doesn't match its definition", name);
      }
      if (argCount) {
        for (let i = 0; i < argCount; i++) {
          args.push(NewcommandUtil.GetParameter(parser, name, params[i + 1]));
        }
        text = ParseUtil.substituteArgs(parser, args, text);
      }
    }
    parser.string = ParseUtil.addArgs(parser, text, parser.string.slice(parser.i));
    parser.i = 0;
    ParseUtil.checkMaxMacros(parser);
  },
  BeginEnv(parser, begin, bdef, edef, n, def) {
    const name = begin.getName();
    if (parser.stack.env["closing"] === name) {
      delete parser.stack.env["closing"];
      const beginN = parser.stack.global["beginEnv"];
      if (beginN) {
        parser.stack.global["beginEnv"]--;
        if (edef) {
          const rest = parser.string.slice(parser.i);
          parser.string = ParseUtil.addArgs(parser, parser.string.substring(0, parser.i), edef);
          parser.Parse();
          parser.string = rest;
          parser.i = 0;
        }
      }
      return parser.itemFactory.create("end").setProperty("name", name);
    }
    if (n) {
      const args = [];
      if (def != null) {
        const optional = parser.GetBrackets(`\\begin{${name}}`);
        args.push(optional == null ? def : optional);
      }
      for (let i = args.length; i < n; i++) {
        args.push(parser.GetArgument(`\\begin{${name}}`));
      }
      bdef = ParseUtil.substituteArgs(parser, args, bdef);
      edef = ParseUtil.substituteArgs(parser, [], edef);
    }
    parser.string = ParseUtil.addArgs(parser, bdef, parser.string.slice(parser.i));
    parser.i = 0;
    parser.stack.global["beginEnv"] = (parser.stack.global["beginEnv"] || 0) + 1;
    return parser.itemFactory.create("beginEnv").setProperty("name", name);
  },
  Macro: BaseMethods_default.Macro
};
var NewcommandMethods_default = NewcommandMethods;

// node_modules/@mathjax/src/mjs/input/tex/newcommand/NewcommandMappings.js
new CommandMap("Newcommand-macros", {
  newcommand: NewcommandMethods_default.NewCommand,
  renewcommand: NewcommandMethods_default.NewCommand,
  newenvironment: NewcommandMethods_default.NewEnvironment,
  renewenvironment: NewcommandMethods_default.NewEnvironment,
  def: NewcommandMethods_default.MacroDef,
  let: NewcommandMethods_default.Let
});

// node_modules/@mathjax/src/mjs/input/tex/newcommand/NewcommandConfiguration.js
function NewcommandConfig(_config, jax) {
  if (jax.parseOptions.packageData.has("newcommand")) {
    return;
  }
  jax.parseOptions.packageData.set("newcommand", {});
  new DelimiterMap(NewcommandTables.NEW_DELIMITER, ParseMethods_default.delimiter, {});
  new CommandMap(NewcommandTables.NEW_COMMAND, {});
  new EnvironmentMap(NewcommandTables.NEW_ENVIRONMENT, ParseMethods_default.environment, {});
  jax.parseOptions.handlers.add({
    [HandlerType.CHARACTER]: [],
    [HandlerType.DELIMITER]: [NewcommandTables.NEW_DELIMITER],
    [HandlerType.MACRO]: [
      NewcommandTables.NEW_DELIMITER,
      NewcommandTables.NEW_COMMAND
    ],
    [HandlerType.ENVIRONMENT]: [NewcommandTables.NEW_ENVIRONMENT]
  }, {}, NewcommandPriority);
}
var NewcommandConfiguration = Configuration.create("newcommand", {
  [ConfigurationType.HANDLER]: {
    macro: ["Newcommand-macros"]
  },
  [ConfigurationType.ITEMS]: {
    [BeginEnvItem.prototype.kind]: BeginEnvItem
  },
  [ConfigurationType.OPTIONS]: {
    maxMacros: 1e3,
    protectedMacros: ["begingroupSandbox"]
  },
  [ConfigurationType.CONFIG]: NewcommandConfig
});

// node_modules/@mathjax/src/mjs/input/tex/ams/AmsConfiguration.js
var AmsTags = class extends AbstractTags {
};
var AmsConfiguration = Configuration.create("ams", {
  [ConfigurationType.HANDLER]: {
    [HandlerType.CHARACTER]: ["AMSmath-operatorLetter"],
    [HandlerType.DELIMITER]: ["AMSsymbols-delimiter", "AMSmath-delimiter"],
    [HandlerType.MACRO]: [
      "AMSsymbols-mathchar0mi",
      "AMSsymbols-mathchar0mo",
      "AMSsymbols-delimiter",
      "AMSsymbols-macros",
      "AMSmath-mathchar0mo",
      "AMSmath-macros",
      "AMSmath-delimiter"
    ],
    [HandlerType.ENVIRONMENT]: ["AMSmath-environment"]
  },
  [ConfigurationType.ITEMS]: {
    [MultlineItem.prototype.kind]: MultlineItem,
    [FlalignItem.prototype.kind]: FlalignItem
  },
  [ConfigurationType.TAGS]: { ams: AmsTags },
  [ConfigurationType.OPTIONS]: {
    multlineWidth: "",
    ams: {
      operatornamePattern: /^[-*a-zA-Z0-9]+/,
      multlineWidth: "100%",
      multlineIndent: "1em"
    }
  },
  [ConfigurationType.CONFIG]: NewcommandConfig
});

// mathjax-sidecar.mjs
var adaptor = liteAdaptor({ fontSize: 16 });
RegisterHTMLHandler(adaptor);
var tex = new TeX({
  packages: ["base", "ams", "newcommand"],
  formatError(_jax, error) {
    throw error;
  }
});
var document = mathjax.document("", { InputJax: tex });
var visitor = new SerializedMmlVisitor();
var lines = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of lines) {
  if (!line.trim()) continue;
  let request;
  try {
    request = JSON.parse(line);
    if (request.protocol !== 1) throw new Error("Unsupported protocol");
    if (typeof request.tex !== "string") throw new Error("tex must be a string");
    if (request.tex.length > Math.min(request.max_expression_chars || 1e5, 1e5)) {
      throw new Error("Equation exceeds maximum length");
    }
    const tree = document.convert(request.tex, {
      display: Boolean(request.display),
      em: 16,
      ex: 8,
      containerWidth: 1280,
      end: STATE.CONVERT
    });
    tree.walkTree((node) => {
      node.attributes?.unset("data-latex");
      node.attributes?.unset("data-latex-item");
    });
    const mathml = visitor.visitTree(tree, document);
    process.stdout.write(JSON.stringify({
      protocol: 1,
      version: mathjax.version,
      mathml,
      normalized_tex: request.tex,
      warnings: [],
      packages: ["base", "ams", "newcommand"]
    }) + "\n");
  } catch (error) {
    process.stdout.write(JSON.stringify({
      protocol: 1,
      error: error instanceof Error ? error.message : String(error)
    }) + "\n");
  }
}
