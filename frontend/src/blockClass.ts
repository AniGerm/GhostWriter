import { Extension } from "@tiptap/core";

/** Behält Klassen an Überschrift und Absatz, damit der Befundkopf erhalten bleibt. */
export const BlockClass = Extension.create({
  name: "blockClass",

  addGlobalAttributes() {
    return [
      {
        types: ["heading", "paragraph"],
        attributes: {
          class: {
            default: null,
            parseHTML: (element: HTMLElement) => element.getAttribute("class"),
            renderHTML: (attributes: { class?: string | null }) => {
              if (!attributes.class) return {};
              return { class: attributes.class };
            },
          },
        },
      },
    ];
  },
});
