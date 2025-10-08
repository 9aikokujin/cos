export default (instance) => ({
  authTG(token) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "GET",
      url: "/users/me",
    }).then((response) => response.data);
  },
  register(data, token) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "POST",
      url: "/users/register",
      data,
    }).then((response) => {
      response.data;
    });
  },
  social(data, token) {
    return instance({
      headers: {
        Authorization: `Bearer ${token}`,
      },
      method: "POST",
      url: "/channels/",
      data,
    }).then(() => {
      return { success: true };
    });
  },
});
