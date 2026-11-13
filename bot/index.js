import { BubbleBot, InlineKeyboard } from "@jeejio-bubble/bot/sdk";
import PixelMugS1 from "@jeejio-bubble/bot/devices/pixelmug-s1";

const token = requiredEnv("BOT_TOKEN");
const mpsID = requiredEnv("STUDIO_MPS_ID");
const mpsVersion = requiredEnv("STUDIO_MPS_VERSION");
const mpsLaunchConfig = {
  id: mpsID,
  version: mpsVersion,
};
const webAppUrl = withMpsLaunchConfig(requiredEnv("STUDIO_WEBAPP_URL"));

function requiredEnv(name) {
  const value = String(process.env[name] || '').trim();
  if (!value) throw new Error(`Missing required environment variable: ${name}`);
  return value;
}

const messages = {
  "zh-CN": {
    bindContent: "\u7ed1\u5b9a PixelMug \u540e\u5373\u53ef\u4f7f\u7528\u756a\u8304\u65f6\u949f\u3002",
    bindButton: "\u7ed1\u5b9a PixelMug",
    addedIntro: "Hello, I am the Pomodoro Timer app agent. I help you configure focus duration, break time, and alert sounds, then sync the workflow to PixelMug so it can run locally. Before you start, please bind your PixelMug.",
    openButton: "\u6253\u5f00\u756a\u8304\u65f6\u949f",
    intro: "**\u756a\u8304\u65f6\u949f**\n\n\u8bbe\u7f6e\u4e13\u6ce8\u65f6\u957f\u3001\u4f11\u606f\u65f6\u95f4\u548c\u63d0\u9192\u97f3\u6548\uff0c\u5e76\u540c\u6b65\u5230 PixelMug\u3002\u540c\u6b65\u540e\uff0c\u8bbe\u5907\u4f1a\u5728\u672c\u5730\u8fd0\u884c\u4e13\u6ce8\u548c\u4f11\u606f\u6d41\u7a0b\u3002\n\n\u70b9\u51fb\u4e0b\u65b9\u6309\u94ae\u6253\u5f00 WebApp\u3002",
    commands: "\u547d\u4ee4\uff1a/bindDevice\uff0c/pomodoro",
    commandBind: "\u7ed1\u5b9a PixelMug",
    commandPomodoro: "\u6253\u5f00\u756a\u8304\u65f6\u949f",
  },
  "en-US": {
    bindContent: "Bind a PixelMug to use PomodoroTimer.",
    bindButton: "Bind PixelMug",
    addedIntro: "你好，我是番茄时钟应用智能体。我会帮助你设置专注时长、休息时间和提醒音效，并同步到 PixelMug，让设备在本地运行专注与休息流程。使用前，请先绑定你的 PixelMug。",
    openButton: "Open PomodoroTimer",
    intro: "**PomodoroTimer**\n\nSet your focus duration and sync the timer to PixelMug. After syncing, the cup can run the focus and break flow locally.\n\nTap below to open the WebApp.",
    commands: "Commands: /bindDevice, /pomodoro",
    commandBind: "Bind PixelMug",
    commandPomodoro: "Open PomodoroTimer",
  },
};

const pixelMug = new PixelMugS1();
const bot = new BubbleBot(token, {
  apiBaseUrl: process.env.BOT_API_BASE_URL,
  webAppDeviceAccess: "any",
});

bot.registerDevices([pixelMug]);

bot.on("error", async (ctx) => {
  console.error("[pomodoro-bot]", ctx.error || ctx);
});

bot.on("contact_added", async (ctx) => {
  await sendAddedIntro(ctx);
});

bot.on("joined_group", async (ctx) => {
  await sendAddedIntro(ctx, { mentionOnly: false });
});

bot.on("message", async (ctx) => {
  const locale = localeFromContext(ctx);
  const command = extractCommand(ctx.message?.content || ctx.message?.text || "");

  if (command === "/bindDevice" || command === "/attachdevice") {
    await sendBindDevice(ctx, locale);
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

function sendAddedIntro(ctx, options = {}) {
  const locale = localeFromContext(ctx);
  return ctx.sendBindDevice({
    content: text(locale, "addedIntro"),
    actionButtonTitle: text(locale, "bindButton"),
    ...options,
  });
}

function sendBindDevice(ctx, locale = localeFromContext(ctx)) {
  return ctx.sendBindDevice({
    content: text(locale, "bindContent"),
    actionButtonTitle: text(locale, "bindButton"),
  });
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





