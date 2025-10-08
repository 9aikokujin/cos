export default (instance) => ({
  getAll({ id, token, type, link, page, size }) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "GET",
      url: "videos/",
      params: {
        id,
        type,
        link,
        page,
        size,
      },
    }).then((response) => response.data);
  },

  create({token, type, link, name}) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "POST",
      url: "videos/",
      data: {
        type,
        link,
        name,
      },
    }).then((response) => response.data);
  },
});
