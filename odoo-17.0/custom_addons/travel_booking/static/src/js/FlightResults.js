import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Plane, Clock, Calendar, Users, Luggage, ArrowRight, ArrowLeft, ThumbsUp, Star } from 'lucide-react';

const FlightResults = ({ searchResults }) => {
  const parseResults = (data) => {
    try {
      const results = typeof data === 'string' ? JSON.parse(data) : data;
      return results?.response?.flights || [];
    } catch (error) {
      console.error('Error parsing flight results:', error);
      return [];
    }
  };

  const formatTime = (dateTimeObj) => {
    if (!dateTimeObj?.time) return '';
    return dateTimeObj.time;
  };

  const formatDate = (dateTimeObj) => {
    if (!dateTimeObj?.date) return '';
    return new Date(dateTimeObj.date).toLocaleDateString('fr-FR');
  };

  const formatScore = (score) => {
    if (score === undefined || score === null) return '0%';
    return `${Math.round(score * 100)}%`;
  };

  const flights = parseResults(searchResults);
  const tripType = searchResults?.parameters?.tripType || 'OneWay';

  // Séparer les vols aller et retour si besoin
  const outboundFlights = flights.filter(f => !f.isReturn);
  const returnFlights = flights.filter(f => f.isReturn);

  if (!flights.length) {
    return (
      <div className="text-center p-8">
        <p className="text-gray-500">Aucun vol trouvé</p>
      </div>
    );
  }

  const FlightCard = ({ flight, isReturn }) => (
    <Card
      className={`hover:shadow-lg transition-shadow ${flight.is_recommended ? 'border-2 border-green-500' : ''}`}
    >
      <CardContent className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* En-tête avec compagnie et recommandation */}
          <div className="flex items-center space-x-4">
            <Plane className="w-6 h-6 text-blue-500" />
            <div>
              <h3 className="text-lg font-semibold">{flight.airlines?.full}</h3>
              <p className="text-sm text-gray-600">Vol {flight.flightNumber}</p>
            </div>
          </div>

          {/* Prix et score de recommandation */}
          <div className="text-right">
            <p className="text-2xl font-bold text-green-600">
              {flight.price} {flight.currency}
            </p>
            <div className="flex flex-col items-end">
              {flight.is_recommended && (
                <div className="flex items-center text-green-600 font-medium bg-green-100 px-2 py-1 rounded-full text-sm mt-1">
                  <ThumbsUp className="w-4 h-4 mr-1" />
                  Recommandé
                </div>
              )}
              {typeof flight.recommendation_score === 'number' && (
                <div className="mt-2 w-full max-w-xs">
                  <div className="flex justify-between items-center mb-1">
                    <span className="text-xs text-gray-500">Score de matching</span>
                    <span className="text-xs font-semibold">{formatScore(flight.recommendation_score)}</span>
                  </div>
                  <Progress
                    value={flight.recommendation_score * 100}
                    className="h-2"
                    indicatorClassName={flight.is_recommended ? "bg-green-500" : "bg-blue-500"}
                  />
                </div>
              )}
            </div>
          </div>

          {/* Horaires et aéroports */}
          <div className="flex items-center space-x-4 col-span-2">
            <div className="flex-1">
              <p className="text-lg font-semibold">{formatTime(flight.departDateTime)}</p>
              <p className="text-sm text-gray-600">{formatDate(flight.departDateTime)}</p>
              <p className="text-sm">{isReturn ? flight.destinationAirport : flight.originAirport}</p>
            </div>

            <div className="flex flex-col items-center">
              <Clock className="w-5 h-5 text-gray-400" />
              <p className="text-sm text-gray-500">{flight.duration}</p>
              <div className="relative w-full h-0.5 bg-gray-200 my-2">
                <div className="absolute inset-0 flex items-center justify-center">
                  <Plane className={`w-4 h-4 text-blue-500 ${isReturn ? 'transform rotate-180' : ''}`} />
                </div>
              </div>
            </div>

            <div className="flex-1 text-right">
              <p className="text-lg font-semibold">{formatTime(flight.arrivalDateTime)}</p>
              <p className="text-sm text-gray-600">{formatDate(flight.arrivalDateTime)}</p>
              <p className="text-sm">{isReturn ? flight.originAirport : flight.destinationAirport}</p>
            </div>
          </div>

          {/* Informations supplémentaires */}
          <div className="grid grid-cols-3 gap-4 col-span-2">
            <div className="flex items-center space-x-2">
              <Luggage className="w-5 h-5 text-gray-400" />
              <span className="text-sm">
                Bagages: {flight.baggageWeight} {flight.baggageUnit}
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <Users className="w-5 h-5 text-gray-400" />
              <span className="text-sm">
                Places: {flight.seatsRemaining || 'N/A'}
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <Star className="w-5 h-5 text-gray-400" />
              <span className="text-sm">
                Classe: {flight.cabin || flight.travel_class || 'Economy'}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div className="space-y-6 w-full max-w-4xl mx-auto p-4">
      {/* Section vols aller */}
      <div>
        <h3 className="text-xl font-semibold mb-4 flex items-center">
          <ArrowRight className="mr-2 text-blue-500" />
          Vols aller
        </h3>
        <div className="space-y-4">
          {outboundFlights.map((flight, index) => (
            <FlightCard key={`outbound-${index}`} flight={flight} isReturn={false} />
          ))}
        </div>
      </div>

      {/* Section vols retour (si aller-retour) */}
      {tripType === 'RoundTrip' && returnFlights.length > 0 && (
        <div>
          <h3 className="text-xl font-semibold mb-4 flex items-center">
            <ArrowLeft className="mr-2 text-blue-500" />
            Vols retour
          </h3>
          <div className="space-y-4">
            {returnFlights.map((flight, index) => (
              <FlightCard key={`return-${index}`} flight={flight} isReturn={true} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default FlightResults;