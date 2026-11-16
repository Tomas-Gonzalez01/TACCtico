export default function ({ data, parentElement, setTriggerValue }) {
  const root = parentElement.querySelector(".offer-list");
  root.replaceChildren();

  function element(tag, text, className) {
    const item = document.createElement(tag);
    if (text) item.textContent = text;
    if (className) item.className = className;
    return item;
  }

  for (const offer of data.offers) {
    const card = element("article");
    const addOffer = () => setTriggerValue("add_offer", offer.key);
    card.ondblclick = (event) => {
      if (!event.target.closest("a, button")) {
        event.preventDefault();
        addOffer();
      }
    };

    const heading = element("div", null, "offer-heading");
    const product = element("div", null, "offer-product");
    product.append(element("strong", offer.title), element("span", offer.seller, "offer-seller"));
    heading.append(product, element("strong", offer.price, "offer-price"));

    const figures = element("div", offer.quantities, "offer-numbers");
    figures.append(element("span", offer.unit_price, "offer-numbers"));

    const actions = element("div", null, "offer-actions");
    const button = element("button", "Agregar a la lista");
    button.type = "button";
    button.setAttribute("aria-label", `Agregar a la lista: ${offer.title} · ${offer.seller} · ${offer.price}`);
    button.onclick = addOffer;
    const link = element("a", "Ver publicación");
    link.href = offer.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    actions.append(button, link);

    card.append(heading, figures, actions);
    root.append(card);
  }
}
