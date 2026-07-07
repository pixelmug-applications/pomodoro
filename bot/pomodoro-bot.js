import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, normalize, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { BubbleBot, InlineKeyboard } from "../../jeejio-bubble/sdk/BubbleSDK.js";
import PixelMug from "../../jeejio-bubble/devices/PixelMug_1.1.js";
import { apiBaseUrl, token } from "./config.pub.js";

const staticPort = Number(process.env.WEBAPP_PORT || 8893);
const webAppHost = process.env.WEBAPP_HOST || localAddressHint();
const generatedWebAppUrl = `http://${webAppHost}:${staticPort}/index.html`;
const mpsLaunchConfig = {
  id: process.env.MPS_ID || "4514905089",
  version: process.env.MPS_VERSION || "1.0.1",
};
const webAppUrl = withMpsLaunchConfig(process.env.WEBAPP_URL || generatedWebAppUrl);
const shouldServeStatic = !process.env.WEBAPP_URL;

const messages = {
  "zh-CN": {
    bindContent: "\u7ed1\u5b9a PixelMug \u540e\u5373\u53ef\u4f7f\u7528\u756a\u8304\u65f6\u949f\u3002",
    bindButton: "\u7ed1\u5b9a PixelMug",
    openButton: "\u6253\u5f00\u756a\u8304\u65f6\u949f",
    intro: "**\u756a\u8304\u65f6\u949f**\n\n\u8bbe\u7f6e\u4e13\u6ce8\u65f6\u957f\u3001\u4f11\u606f\u65f6\u95f4\u548c\u63d0\u9192\u97f3\u6548\uff0c\u5e76\u540c\u6b65\u5230 PixelMug\u3002\u540c\u6b65\u540e\uff0c\u8bbe\u5907\u4f1a\u5728\u672c\u5730\u8fd0\u884c\u4e13\u6ce8\u548c\u4f11\u606f\u6d41\u7a0b\u3002\n\n\u70b9\u51fb\u4e0b\u65b9\u6309\u94ae\u6253\u5f00 WebApp\u3002",
    commands: "\u547d\u4ee4\uff1a/bindDevice\uff0c/pomodoro",
    commandBind: "\u7ed1\u5b9a PixelMug",
    commandPomodoro: "\u6253\u5f00\u756a\u8304\u65f6\u949f",
  },
  "en-US": {
    bindContent: "Bind a PixelMug to use PomodoroTimer.",
    bindButton: "Bind PixelMug",
    openButton: "Open PomodoroTimer",
    intro: "**PomodoroTimer**\n\nSet your focus duration and sync the timer to PixelMug. After syncing, the cup can run the focus and break flow locally.\n\nTap below to open the WebApp.",
    commands: "Commands: /bindDevice, /pomodoro",
    commandBind: "Bind PixelMug",
    commandPomodoro: "Open PomodoroTimer",
  },
};

if (!token) {
  throw new Error("Missing BUBBLE_BOT_TOKEN. Set it before running this bot.");
}

const pixelMug = new PixelMug();
pixelMug.compatible = ["PixelMugS1"];
const bot = new BubbleBot(token, {
  apiBaseUrl,
  debug: process.env.DEBUG !== "false",
  observeWebAppDeviceCalls: true,
  webAppDeviceAccess: "any",
});

bot.registerDevices([pixelMug]);

bot.on("error", async (ctx) => {
  console.error("[pomodoro-bot]", ctx.error || ctx);
});

bot.on("web_app_device_call", async (ctx) => {
  const call = ctx.webAppDeviceCall || {};
  console.log("[pomodoro-bot] WebApp device call", {
    direction: call.direction,
    method: call.method,
    slotId: call.slotId,
    deviceId: call.deviceId,
    result: call.result,
  });
});

bot.on("message", async (ctx) => {
  const locale = localeFromContext(ctx);
  const command = extractCommand(ctx.message?.content || ctx.message?.text || "");

  if (command === "/bindDevice" || command === "/attachdevice") {
    await ctx.sendBindDevice({
      content: text(locale, "bindContent"),
      actionButtonTitle: text(locale, "bindButton"),
    });
    return;
  }

  if (command === "/pomodoro" || command === "/webapp" || command === "/start") {
    const keyboard = new InlineKeyboard().url(text(locale, "openButton"), withLocale(webAppUrl, locale));
    await ctx.sendKeyboard(
      text(locale, "intro"),
      keyboard,
      {
        mentionOnly: ctx.chat?.type === "group" ? true : undefined,
      },
    );
    return;
  }

  await ctx.sendText(text(locale, "commands"));
});

if (shouldServeStatic) {
  await startStaticServer();
}

await bot.setCommands([
  {
    command: "bindDevice",
    description: messages["en-US"].commandBind,
    descTranslations: {
      "zh-CN": messages["zh-CN"].commandBind,
      en: messages["en-US"].commandBind,
    },
  },
  {
    command: "pomodoro",
    description: messages["en-US"].commandPomodoro,
    descTranslations: {
      "zh-CN": messages["zh-CN"].commandPomodoro,
      en: messages["en-US"].commandPomodoro,
    },
  },
]);

await bot.start();

console.log("mps-pomodoro bot is running.");
console.log(`WebApp URL: ${webAppUrl}`);

function extractCommand(text) {
  const match = String(text || "").trim().match(/\/[a-zA-Z0-9_-]+(?:@[a-zA-Z0-9_-]+)?/);
  if (!match) return "";
  return match[0].split("@")[0];
}

function localeFromContext(ctx) {
  const value = ctx.chat?.language || ctx.from?.language || process.env.APP_LOCALE;
  return normalizeLocale(value);
}

function normalizeLocale(value) {
  const source = String(value || "").toLowerCase();
  return source.startsWith("zh") ? "zh-CN" : "en-US";
}

function text(locale, key) {
  return messages[locale]?.[key] || messages["en-US"][key] || key;
}

function startStaticServer() {
  const distRoot = fileURLToPath(new URL("../webapp/dist", import.meta.url));

  const server = createServer(async (req, res) => {
    try {
      const requestUrl = new URL(req.url || "/", `http://${req.headers.host || "localhost"}`);
      const pathname = requestUrl.pathname === "/" ? "/index.html" : requestUrl.pathname;
      const filePath = normalize(join(distRoot, decodeURIComponent(pathname)));
      const rel = relative(distRoot, filePath);

      if (rel.startsWith("..")) {
        sendStatus(res, 403, "Forbidden");
        return;
      }

      const info = await stat(filePath);
      if (!info.isFile()) {
        sendStatus(res, 404, "Not found");
        return;
      }

      res.writeHead(200, {
        "content-type": contentType(filePath),
        "cache-control": "no-store",
      });
      createReadStream(filePath).pipe(res);
    } catch (error) {
      const message = String(error?.code || error?.message || error);
      if (message.includes("ENOENT")) {
        sendStatus(res, 404, "Build not found. Run npm run build first.");
        return;
      }
      sendStatus(res, 404, "Not found");
    }
  });

  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(staticPort, "0.0.0.0", () => {
      server.off("error", reject);
      console.log(`Static WebApp server listening on http://0.0.0.0:${staticPort}`);
      resolve(server);
    });
  });
}

function sendStatus(res, status, body) {
  res.writeHead(status, { "content-type": "text/plain; charset=utf-8" });
  res.end(body);
}

function contentType(filePath) {
  switch (extname(filePath)) {
    case ".html":
      return "text/html; charset=utf-8";
    case ".js":
      return "text/javascript; charset=utf-8";
    case ".css":
      return "text/css; charset=utf-8";
    case ".json":
      return "application/json";
    case ".svg":
      return "image/svg+xml";
    case ".png":
      return "image/png";
    case ".jpg":
    case ".jpeg":
      return "image/jpeg";
    case ".mp3":
      return "audio/mpeg";
    case ".ogg":
      return "audio/ogg";
    default:
      return "application/octet-stream";
  }
}

function withMpsLaunchConfig(url) {
  const next = new URL(url);
  next.searchParams.set("mps_id", mpsLaunchConfig.id);
  next.searchParams.set("mps_version", mpsLaunchConfig.version);
  return next.toString();
}

function withLocale(url, locale) {
  const next = new URL(url);
  next.searchParams.set("lang", locale);
  return next.toString();
}

function localAddressHint() {
  return process.env.HOST || "127.0.0.1";
}