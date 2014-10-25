from django.http.response import HttpResponse
from models import Sample, Trip
from django.http import HttpResponse,Http404
from django.core import serializers
from django.db.models import Q
import itertools, datetime, json
from django.utils.timezone import make_naive, get_current_timezone

def json_resp(obj,status=200):
    import json
    return HttpResponse(content=json.dumps(obj),content_type='application/json')

def show_sample(req):
    try:
        sample = Sample.objects.filter(stop_id=req.GET.get('stop_id'), valid=True, is_real_stop=True)

        response = HttpResponse(serializers.serialize('json', sample))
        print(response)
        return response
    except Exception as e:
        print(e)

def get_departure_hour(sample):
    return make_naive(sample.exp_departure, get_current_timezone()).hour

def get_stops(req):
    stops = Sample.objects.filter(is_real_stop=True).values('stop_id','stop_name').distinct().order_by('stop_name')
    return json_resp(list(stops))

def get_relevant_routes(origin, destination, fromTime, toTime):
        routes = Trip.objects.raw('''SELECT id, stop_ids
        FROM public.data_trip
        WHERE valid
        AND ARRAY[%s::int,%s::int] <@ stop_ids
        ''', [origin, destination])

        trips = [route.id for route in routes if route.stop_ids.index(int(origin)) < route.stop_ids.index(int(destination))]

        samples = list(Sample.objects.filter(Q(stop_id=destination) | Q(stop_id=origin)).filter(trip_name__in=trips).order_by('trip_name'))

        filteredSamples = []
        for firstSample, secondSample in itertools.izip(samples[::2], samples[1::2]):
            # if(firstSample.id == 14):
            #     print(firstSample.id, make_naive(firstSample.exp_departure, get_current_timezone()))
            if (firstSample.stop_id == origin and fromTime <= get_departure_hour(firstSample) <= toTime) or \
                    (secondSample.stop_id == origin and fromTime <= get_departure_hour(secondSample) <= toTime):
                filteredSamples.append((firstSample, secondSample) if firstSample.stop_id == origin else (secondSample, firstSample))

        return filteredSamples


def get_relevant_routes_from_request(req):
    try:
        origin = int(req.GET.get('from'))
        destination = int(req.GET.get('to'))
        fromTime = int(req.GET.get('from_time') or 0)
        toTime = int(req.GET.get('to_time') or 23)

        return get_relevant_routes(origin, destination, fromTime, toTime)

    except Exception as e:
        print(e)


def get_delay(req):
    samples = get_relevant_routes_from_request(req)
    size = len(samples)
    delays = [sample[1].delay_arrival or 0 for sample in samples]
    average = sum(delays) / size
    minimum = min(delays)
    maximum = max(delays)

    minTrips = [sample[1].trip_name for sample in samples if sample[1].delay_arrival == minimum]
    maxTrips = [sample[1].trip_name for sample in samples if sample[1].delay_arrival == maximum]

    res = {'min': {
        'duration': minimum,
        'trips': minTrips
    }, 'max': {
        'duration': maximum,
        'trips': maxTrips
    },
        'average': average
    }
    return HttpResponse(json.dumps(res))

def get_delay_over_total_duration(req):
    samples = get_relevant_routes_from_request(req)
    delay = 0
    duration = datetime.timedelta()
    for sample in samples:
        if len(sample) != 2:
            continue

        delay += (sample[1].delay_arrival or 0)
        duration += sample[1].exp_arrival - sample[0].exp_departure

    return HttpResponse(delay / duration.total_seconds())

def get_trip(req,trip_id):
    from models import Trip
    try:
        trip = Trip.objects.get(id=trip_id)
    except Trip.DoesNotExist:
        return json_resp({'error' : '404',
                          'trip_id' : trip_id},
                         status=404)
    return json_resp(trip.to_json());
# def get_delay_buckets(req):
#     if req.GET.get('from'): # TODO: check all routes
#         samples = get_relevant_routes_from_request(req)
#         histogram = {}
#         delays = [sample[1].delay_arrival or 0 for sample in samples]
#         for sample in sample



#  from station to station, from time of day to time of day: delay average, % delays over threshold, delay/totalDuration
#  buckets of delays
# correlation between early lates in the routes
# find direction of a route,compare the two directions