class CampaignMiddleware:
    """
    Remembers a campaign code (?c=CODE or utm_campaign) and a referral code (?ref=CODE) from the visitor's
    landing page, so the trial request they send later is credited to it (decisions P5-7, P5-8).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "GET" and not request.path.startswith(
            ("/desk/", "/cms/", "/api/", "/en/desk/", "/ar/desk/")
        ):
            campaign = request.GET.get("c") or request.GET.get("utm_campaign")
            ref = request.GET.get("ref")
            if campaign:
                request.session["campaign"] = campaign[:30]
            if ref:
                request.session["ref"] = ref[:10]
        return self.get_response(request)
