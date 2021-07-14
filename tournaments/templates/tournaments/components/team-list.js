const elements = document.getElementsByClassName("sortable-team")
for (let element of elements) {
  new Sortable(element, {
      group: 'teams',
      animation: 150,
      ghostClass: "bg-primary",
  });
}

function debounce(timeout, func){
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => { func.apply(this, args); }, timeout);
  };
}

$("#rider_query").on("input", debounce(250, function () {
  const options = {};
  options.url = "{% url 'tournaments:rider_search' tournament.id %}";
  options.type = "GET";
  options.data = { "rider_query": $("#rider_query").val() };
  options.dataType = "json";
  options.success = function (data) {
    const riderList = $("#rider_list")
    riderList.empty();
    for(let i=0; i<data.length; i++)
    {
      riderList.append(`<option value="${data[i].username}"></option>`);
    }
  };
  $.ajax(options);
}));