import lang from "./_zh.js";
const strings = { title: "小芒图案库", website: "/patterns/", pages: [], versions: [], langs: [] };
const pageDetails = (page) => ({
  title: page === "index" ? strings.title : page + " · " + strings.title,
  url: "/patterns/" + (page === "index" ? "" : page + "/"),
  keywords: lang.strings.keywords,
  desc: lang.strings.description,
  image: "/patterns/logo-512.png",
  versions: [],
});
// Original gallery palettes; keep these separate from metadata.
const lightColors = [
  "hsla(0,0%,100%,1)", "hsla(258.5,59.4%,59.4%,1)",
  "hsla(339.6,82.2%,51.6%,1)", "hsla(198.7,97.6%,48.4%,1)", "hsla(47,80.9%,61%,1)",
];
const darkColors = [
  "hsla(240,6.7%,17.6%,1)", "hsla(47,80.9%,61%,1)",
  "hsla(4.1,89.6%,58.4%,1)", "hsla(186.8,100%,41.6%,1)", "hsla(258.5,59.4%,59.4%,1)",
];
export default { strings, pageDetails, lightColors, darkColors };
