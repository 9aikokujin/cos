export default (instance) => ({
  getVideos({ user_id, id, type, link, name, page, size = 10 }) {
    return instance({
      method: "GET",
      url: "/videos/",
      params: {
        user_id,
        id,
        type,
        link,
        name,
        page,
        size: size,
      },
    }).then((response) => response.data);
  },
  deleteVideo(id) {
    return instance({
      method: "DELETE",
      url: `/videos/${id}`,
    });
  },
});
